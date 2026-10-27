"""Fail-closed helpers for tenant membership cardinality."""
from fastapi import HTTPException


def require_exactly_one_membership(query, *, missing_detail: str, ambiguous_detail: str):
    """Return the sole membership row; deny both missing and ambiguous membership.

    The query is capped at two rows so duplicate legacy data cannot influence
    authorization based on database row ordering.
    """
    rows = query.limit(2).all()
    if not rows:
        raise HTTPException(status_code=403, detail=missing_detail)
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail=ambiguous_detail)
    return rows[0]
