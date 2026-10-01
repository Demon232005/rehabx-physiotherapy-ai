"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    hash_password,
    verify_password_reset_token,
)
from app.models import User
from app.schemas import (
    MessageOut,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services import audit
from app.services.auth import authenticate
from app.services.email import send_password_reset_email
from app.api.deps import CurrentUser, DbDep
from app.utils.ratelimit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))],
)
def register(payload: UserRegister, db: DbDep, request: Request) -> User:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="patient",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit.log(
        db,
        user_id=user.id,
        action="auth.register",
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))],
)
def login(payload: UserLogin, db: DbDep, request: Request) -> TokenResponse:
    user = authenticate(db, payload.email, payload.password)
    settings = get_settings()
    token = create_access_token(user.id, extra={"role": user.role})

    audit.log(
        db,
        user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/logout", response_model=MessageOut)
def logout(user: CurrentUser, db: DbDep) -> MessageOut:
    audit.log(db, user_id=user.id, action="auth.logout")
    return MessageOut(message="Logged out")


@router.post(
    "/password-reset/request",
    response_model=MessageOut,
    dependencies=[Depends(rate_limit(max_requests=3, window_seconds=60))],
)
def request_password_reset(payload: PasswordResetRequest, db: DbDep) -> MessageOut:
    email = payload.email.lower()
    settings = get_settings()
    reset_token = create_password_reset_token(email)

    response = MessageOut(message="If the email exists, a reset link has been sent.")

    if settings.debug:
        return MessageOut(
            message=f"If the email exists, a reset link has been sent. [dev token: {reset_token}]"
        )

    user = db.scalar(select(User).where(User.email == email))
    if user and not send_password_reset_email(email, reset_token):
        # Email delivery failed (or SMTP unconfigured). The generic
        # response is kept so we never reveal whether the account exists.
        audit.log(
            db,
            action="auth.password_reset_email_failed",
            entity_type="user",
            entity_id=user.id,
        )

    return response


@router.post("/password-reset/confirm", response_model=MessageOut)
def confirm_password_reset(payload: PasswordResetConfirm, db: DbDep) -> MessageOut:
    try:
        email = verify_password_reset_token(payload.token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return MessageOut(message="Password has been reset successfully")
