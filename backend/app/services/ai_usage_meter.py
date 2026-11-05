"""Atomic, tenant-scoped AI usage reservations for billable provider calls."""
from sqlalchemy import and_, case, func, or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.types import Date

from app.models.billing import Subscription


USAGE_POLICIES = {
    "ai_chat_uploads_this_month": {"trial": 10, "pro": 200},
    "invoice_ocr_this_month": {"trial": 20, "pro": 500},
}


class UsageLimitExceeded(Exception):
    """Raised when the tenant is inactive or its monthly AI allowance is exhausted."""


def reserve_ai_usage(db, org_id, usage_key: str) -> dict:
    """Atomically reserve one unit, rolling counters into the current month.

    PostgreSQL's unique org_id constraint and UPDATE ... RETURNING ensure
    concurrent requests cannot overspend a tenant's allowance.
    """
    if usage_key not in USAGE_POLICIES:
        raise ValueError("Unsupported AI usage counter.")

    counter = getattr(Subscription, usage_key)
    current_month = func.date_trunc("month", func.now()).cast(Date)
    try:
        db.execute(
            pg_insert(Subscription)
            .values(org_id=org_id, plan="trial", status="active", usage_period_start=current_month)
            .on_conflict_do_nothing(index_elements=[Subscription.org_id])
        )
        policy = USAGE_POLICIES[usage_key]
        within_plan_limit = or_(
            Subscription.plan == "enterprise",
            and_(Subscription.plan == "trial", counter < policy["trial"]),
            and_(Subscription.plan == "pro", counter < policy["pro"]),
        )
        new_count = case(
            (Subscription.usage_period_start < current_month, 1),
            else_=counter + 1,
        )
        statement = (
            update(Subscription)
            .where(
                Subscription.org_id == org_id,
                Subscription.status == "active",
                or_(Subscription.usage_period_start < current_month, within_plan_limit),
            )
            .values({usage_key: new_count, "usage_period_start": current_month})
            .returning(Subscription.plan, counter)
        )
        row = db.execute(statement).first()
        if row is None:
            db.rollback()
            raise UsageLimitExceeded(
                "AI usage is unavailable: the subscription is inactive or its monthly plan limit has been reached."
            )
        db.commit()
        return {"plan": row[0], "current_usage": row[1]}
    except UsageLimitExceeded:
        raise
    except Exception:
        db.rollback()
        raise
