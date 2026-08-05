"""
Module 10: Auth — OTP login endpoints, consumed by the frontend's NextAuth
"otp" credentials provider. Google and Microsoft OAuth are handled entirely
by NextAuth on the frontend (see frontend/app/api/auth/[...nextauth]/route.ts)
and don't need backend endpoints — NextAuth talks to those providers directly.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.security import generate_otp, verify_otp, send_otp_via_email_or_sms, create_access_token
from app.core.db import get_db

router = APIRouter()


class OtpRequestBody(BaseModel):
    email: EmailStr


@router.post("/otp/request")
def request_otp(req: OtpRequestBody):
    otp = generate_otp(req.email)
    send_otp_via_email_or_sms(req.email, otp)
    response = {"message": f"OTP sent to {req.email}"}
    if True:  # DEV CONVENIENCE: remove this block once a real SMS/email provider is wired up
        response["dev_otp"] = otp
    return response


class OtpVerifyBody(BaseModel):
    email: EmailStr
    otp: str


@router.post("/otp/verify")
def verify_otp_endpoint(req: OtpVerifyBody, db: Session = Depends(get_db)):
    if not verify_otp(req.email, req.otp):
        raise HTTPException(401, detail="Invalid or expired OTP")

    # Get-or-create the user row so repeated logins resolve to the same
    # identity — required for org membership / RBAC lookups to work at all
    # (previously this issued a fresh random uuid on every login, which
    # would never match any org_memberships row).
    from app.models.auth_user import User

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        user = User(email=req.email, full_name=req.email.split("@")[0], auth_provider="otp")
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=req.email)
    return {"user_id": str(user.id), "full_name": user.full_name, "access_token": token}
