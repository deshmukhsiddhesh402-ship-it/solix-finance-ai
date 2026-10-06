"""
Module: Enterprise Features — API layer.

Wires together RBAC (rbac_engine.py), audit logging (audit_engine.py), and
API keys (api_key_engine.py) into actual endpoints, permission-checked via
`require_permission`, a FastAPI dependency that decodes the caller's JWT,
looks up their role for the given organization, and fails closed if
anything doesn't check out.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.services.rbac_engine import has_permission
from app.services.audit_engine import build_audit_entry
from app.services.api_key_engine import generate_api_key, mask_api_key

router = APIRouter()


@router.get("/permissions-matrix")
def permissions_matrix():
    """Public reference endpoint — shows what each role (Admin/Accountant/
    Auditor) can do. No auth required; this is documentation, not a
    sensitive operation."""
    from app.services.rbac_engine import list_permissions
    return {role: list_permissions(role) for role in ["admin", "accountant", "auditor"]}


def require_permission(resource: str, action: str):
    """Dependency factory: returns a FastAPI dependency that verifies the
    calling user (via Bearer JWT) has `action` permission on `resource`
    within the org given by the `org_id` query/body param. Fails closed —
    any missing token, bad token, or missing membership means 403, not a
    silent pass-through.
    """
    def _dependency(
        org_id: str = Query(...),
        authorization: str = Header(default=""),
        db: Session = Depends(get_db),
    ) -> str:
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, detail="Missing or malformed Authorization header.")
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(401, detail="Invalid or expired token.")
        user_id = payload["sub"]

        from app.models.enterprise import OrgMembership
        from app.models.auth_user import User  # local import — see note below

        try:
            user_uuid = uuid.UUID(str(user_id))
            org_uuid = uuid.UUID(str(org_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(400, detail="Invalid organization identifier.") from exc

        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            raise HTTPException(403, detail="User not found.")
        membership = db.query(OrgMembership).filter(
            OrgMembership.user_id == user.id, OrgMembership.org_id == org_uuid
        ).first()
        if not membership:
            raise HTTPException(403, detail="You are not a member of this organization.")
        if not has_permission(membership.role, resource, action):
            raise HTTPException(403, detail=f"Your role ({membership.role}) cannot {action} {resource}.")
        return str(user.id)
    return _dependency


# ---------------------------------------------------------------------------
# Org memberships (multi-company support)
# ---------------------------------------------------------------------------
class AddMembershipRequest(BaseModel):
    org_id: str
    user_email: str
    role: Literal["admin", "accountant", "auditor"]


@router.post("/memberships")
def add_membership(
    req: AddMembershipRequest, org_id: str = Query(...), db: Session = Depends(get_db),
    _acting_user: str = Depends(require_permission("users", "manage_users")),
):
    if req.org_id != org_id:
        raise HTTPException(400, detail="Request organization must match the authorized organization.")
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    from app.models.enterprise import OrgMembership
    from app.models.auth_user import User

    target_user = db.query(User).filter(User.email == req.user_email).first()
    if not target_user:
        raise HTTPException(404, detail=f"No user found with email {req.user_email}.")

    existing = db.query(OrgMembership).filter(OrgMembership.user_id == target_user.id, OrgMembership.org_id == org_uuid).first()
    if existing:
        raise HTTPException(409, detail="User is already a member of this organization.")
    membership = OrgMembership(user_id=target_user.id, org_id=org_uuid, role=req.role)
    db.add(membership)
    db.commit()
    return {"message": f"{req.user_email} added to organization as {req.role}."}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
@router.get("/audit-log")
def view_audit_log(
    org_id: str = Query(...), limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("audit_log", "view")),
):
    from app.models.enterprise import AuditLog

    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.org_id == org_uuid)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "entries": [
            {"id": str(r.id), "user_id": str(r.user_id) if r.user_id else None, "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "changes": r.changes,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
    }


def log_action(db: Session, org_id: str, user_id: str, action: str, entity_type: str, entity_id: str,
                before: dict | None = None, after: dict | None = None):
    """Call this from other routers (accounting, invoice_ocr, etc.) right
    after a mutating action succeeds, to actually populate the audit trail.
    Not yet wired into every existing endpoint in this pass — see README."""
    from app.models.enterprise import AuditLog

    try:
        org_uuid = uuid.UUID(org_id)
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid organization or user identifier.") from exc

    entry = build_audit_entry(str(user_uuid), str(org_uuid), action, entity_type, entity_id, before, after)
    db.add(AuditLog(
        org_id=org_uuid, user_id=user_uuid, action=entry.action,
        entity_type=entry.entity_type, entity_id=entry.entity_id, changes=entry.changes,
    ))
    db.commit()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
class CreateApiKeyRequest(BaseModel):
    org_id: str
    name: str


@router.post("/api-keys")
def create_api_key(
    req: CreateApiKeyRequest, org_id: str = Query(...), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("api_keys", "create")),
):
    if req.org_id != org_id:
        raise HTTPException(400, detail="Request organization must match the authorized organization.")
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    from app.models.enterprise import ApiKey

    plaintext, hashed = generate_api_key()
    key_row = ApiKey(org_id=org_uuid, name=req.name, hashed_key=hashed, key_prefix_display=mask_api_key(plaintext))
    db.add(key_row)
    db.commit()
    return {
        "id": str(key_row.id),
        "plaintext_key": plaintext,  # shown ONCE — the frontend must warn the user to save it now
        "warning": "This is the only time the full key is shown. Store it securely.",
    }


@router.get("/api-keys")
def list_api_keys(
    org_id: str = Query(...), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("api_keys", "view")),
):
    from app.models.enterprise import ApiKey

    org_uuid = uuid.UUID(org_id)
    rows = db.query(ApiKey).filter(ApiKey.org_id == org_uuid, ApiKey.revoked == False).all()  # noqa: E712
    return {"keys": [
        {"id": str(r.id), "name": r.name, "masked_key": r.key_prefix_display,
         "created_at": r.created_at.isoformat() if r.created_at else None,
         "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None}
        for r in rows
    ]}


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: str, org_id: str = Query(...), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("api_keys", "delete")),
):
    from app.models.enterprise import ApiKey

    org_uuid = uuid.UUID(org_id)
    key_row = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.org_id == org_uuid).first()
    if not key_row:
        raise HTTPException(404, detail="API key not found.")
    key_row.revoked = True
    db.commit()
    return {"message": "API key revoked."}


# ---------------------------------------------------------------------------
# Scheduled reports (data model only — see caveat in models/enterprise.py)
# ---------------------------------------------------------------------------
class ScheduledReportRequest(BaseModel):
    org_id: str
    report_type: str
    frequency: str  # daily, weekly, monthly
    recipient_emails: list[str]


@router.post("/scheduled-reports")
def create_scheduled_report(
    req: ScheduledReportRequest, org_id: str = Query(...), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "create")),
):
    if req.org_id != org_id:
        raise HTTPException(400, detail="Request organization must match the authorized organization.")
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    from app.models.enterprise import ScheduledReport

    report = ScheduledReport(
        org_id=org_uuid, report_type=req.report_type, frequency=req.frequency,
        recipient_emails=req.recipient_emails,
    )
    db.add(report)
    db.commit()
    return {
        "id": str(report.id),
        "message": "Schedule saved. NOTE: actual sending requires a background worker "
                   "(Celery beat) polling this table — not yet wired up; see README.",
    }


# ---------------------------------------------------------------------------
# Notifications (in-app only — no email/SMS/push delivery wired, see model docstring)
# ---------------------------------------------------------------------------
@router.get("/notifications")
def list_notifications(
    org_id: str = Query(...), user_id: str | None = Query(default=None),
    unread_only: bool = Query(default=False), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    from app.models.enterprise import Notification

    if user_id is not None and user_id != _user:
        raise HTTPException(403, detail="Users may only view their own notifications.")
    org_uuid = uuid.UUID(org_id)
    query = db.query(Notification).filter(Notification.org_id == org_uuid, Notification.user_id == _user)
    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712
    rows = query.order_by(Notification.created_at.desc()).limit(50).all()
    return {"notifications": [
        {"id": str(r.id), "title": r.title, "body": r.body, "is_read": r.is_read,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str, org_id: str = Query(...), db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    from app.models.enterprise import Notification

    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    notif = db.query(Notification).filter(
        Notification.id == notification_id, Notification.org_id == org_uuid,
        Notification.user_id == _user,
    ).first()
    if not notif:
        raise HTTPException(404, detail="Notification not found.")
    notif.is_read = True
    db.commit()
    return {"message": "Marked as read."}
