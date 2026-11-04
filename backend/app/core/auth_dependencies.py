"""Reusable JWT-backed user and tenant permission dependencies.

These dependencies use the existing FastAPI access-token format and RBAC
matrix. They do not create or accept a second credential type.
"""
import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.services.rbac_engine import has_permission


def get_authenticated_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Return the active database user for a valid bearer JWT, otherwise 401."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="Authentication required.")

    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not payload or not payload.get("sub"):
        raise HTTPException(401, detail="Invalid or expired authentication token.")

    try:
        user_uuid = uuid.UUID(str(payload["sub"]))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(401, detail="Invalid or expired authentication token.") from exc

    from app.models.auth_user import User

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise HTTPException(401, detail="Invalid or expired authentication token.")
    return user


def require_user_permission(resource: str, action: str) -> Callable:
    """Authorize a user's primary tenant without requiring a tenant query param.

    An optional ``org_id`` is accepted for callers that already supply one;
    it must match the user's primary organization. This lets existing proxies
    that omit tenant parameters keep working while rejecting cross-tenant
    attempts. Membership role permissions are always read from the database.
    """
    def _dependency(
        org_id: str | None = Query(default=None),
        user=Depends(get_authenticated_user),
        db: Session = Depends(get_db),
    ) -> str:
        if user.org_id is None:
            raise HTTPException(403, detail="Access to this feature is not permitted.")

        try:
            primary_org_uuid = uuid.UUID(str(user.org_id))
            requested_org_uuid = uuid.UUID(str(org_id)) if org_id is not None else primary_org_uuid
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(403, detail="Access to this feature is not permitted.") from exc

        if requested_org_uuid != primary_org_uuid:
            raise HTTPException(403, detail="Access to this feature is not permitted.")

        from app.models.enterprise import OrgMembership

        membership = (
            db.query(OrgMembership)
            .filter(OrgMembership.user_id == user.id, OrgMembership.org_id == primary_org_uuid)
            .first()
        )
        if membership is None or not has_permission(membership.role, resource, action):
            raise HTTPException(403, detail="Access to this feature is not permitted.")
        return str(user.id)

    return _dependency
