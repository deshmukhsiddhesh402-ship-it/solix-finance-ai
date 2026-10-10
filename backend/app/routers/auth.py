"""Email OTP login endpoints consumed by the frontend's NextAuth provider."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_otp, verify_otp, discard_otp,
    send_otp_via_email_or_sms, create_access_token,
)
from app.core.db import get_db

router = APIRouter()


class OtpRequestBody(BaseModel):
    email: EmailStr


@router.post("/otp/request")
def request_otp(req: OtpRequestBody):
    try:
        otp = generate_otp(str(req.email))
    except ValueError as exc:
        raise HTTPException(429, detail="Please wait before requesting another OTP.") from exc

    try:
        send_otp_via_email_or_sms(str(req.email), otp)
    except RuntimeError as exc:
        discard_otp(str(req.email))
        raise HTTPException(503, detail="OTP delivery is not configured.") from exc

    response = {"message": "If the address is eligible, an OTP will be sent."}
    if settings.ENV.strip().lower() in {"development", "dev"} and settings.DEV_OTP_ENABLED:
        response["dev_otp"] = otp
    return response


class OtpVerifyBody(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=8, pattern=r"^[0-9]{6,8}$")


@router.post("/otp/verify")
def verify_otp_endpoint(req: OtpVerifyBody, db: Session = Depends(get_db)):
    """Verify OTP and guarantee that every authenticated user has a tenant."""
    if not verify_otp(str(req.email), req.otp):
        raise HTTPException(401, detail="Invalid or expired OTP")

    from app.models.auth_user import Organization, OrgMembership, User

    email = str(req.email)
    user = db.query(User).filter(User.email == email).first()

    if not user:
        organization = Organization(name="Personal Workspace")
        db.add(organization)
        db.flush()

        user = User(
            email=email,
            full_name=email.split("@")[0],
            auth_provider="otp",
            role="owner",
            org_id=organization.id,
        )
        db.add(user)
        db.flush()
        db.add(OrgMembership(user_id=user.id, org_id=organization.id, role="admin"))
        db.commit()
        db.refresh(user)
    elif user.org_id is None:
        # Repair legacy users created before tenant assignment was enforced.
        organization = Organization(name="Personal Workspace")
        db.add(organization)
        db.flush()
        user.org_id = organization.id
        user.role = "owner"
        db.add(OrgMembership(user_id=user.id, org_id=organization.id, role="admin"))
        db.commit()
        db.refresh(user)

    else:
        # Fail closed if a legacy user points at a tenant without a matching membership.
        membership = (
            db.query(OrgMembership)
            .filter(OrgMembership.user_id == user.id, OrgMembership.org_id == user.org_id)
            .first()
        )
        if membership is None:
            raise HTTPException(403, detail="User tenant membership is not configured.")

    token = create_access_token(subject=str(user.id))
    return {
        "user_id": str(user.id),
        "org_id": str(user.org_id) if user.org_id else None,
        "full_name": user.full_name,
        "access_token": token,
    }
