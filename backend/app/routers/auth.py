from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.captcha import verify_captcha
from app.config import get_settings
from app.database import get_db
from app.deps import client_ip, get_current_user
from app.email import send_verification_email
from app.models import AuditLog, EmailVerificationToken, User
from app.rate_limit import clear_failed_logins, is_locked_out, register_failed_login
from app.schemas import LoginRequest, SignupRequest, UserOut
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    response.set_cookie(
        "access_token",
        token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


async def _audit(db: AsyncSession, user_id: str | None, event: str, ip: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, event=event, ip_address=ip, detail=detail))
    await db.commit()


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, request_ip: str = Depends(client_ip), db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(payload.captcha_token, request_ip):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CAPTCHA verification failed")

    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        # Do not reveal whether the account exists; behave as if signup succeeded.
        return UserOut(id="", email=payload.email, is_verified=False, created_at=datetime.now(timezone.utc))

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_verified=False,
        consented_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    raw_token, token_hash = new_opaque_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_ttl_hours),
        )
    )
    await db.commit()
    await db.refresh(user)

    verify_url = f"{settings.frontend_url}/verify?token={raw_token}"
    send_verification_email(user.email, verify_url)
    await _audit(db, user.id, "signup", request_ip)

    return user


@router.get("/verify", response_model=UserOut)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(token)
    record = (
        await db.execute(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash))
    ).scalar_one_or_none()

    if not record or record.used_at is not None or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link")

    user = (await db.execute(select(User).where(User.id == record.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid verification link")

    user.is_verified = True
    record.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest,
    response: Response,
    request_ip: str = Depends(client_ip),
    db: AsyncSession = Depends(get_db),
):
    if not await verify_captcha(payload.captcha_token, request_ip):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CAPTCHA verification failed")

    if await is_locked_out(payload.email, request_ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed login attempts. Try again later.",
        )

    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        await register_failed_login(payload.email, request_ip)
        await _audit(db, user.id if user else None, "login_failed", request_ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email before logging in")

    await clear_failed_logins(payload.email, request_ip)
    _set_session_cookie(response, user.id)
    await _audit(db, user.id, "login_success", request_ip)
    return user


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/", domain=settings.cookie_domain)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
