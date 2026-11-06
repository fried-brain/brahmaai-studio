from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import User, UserSession
from app.core.security import hash_token


def database_session(request: Request):
    factory: sessionmaker[Session] | None = request.app.state.session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    session = factory()
    try:
        yield session
    finally:
        session.close()


def current_session(request: Request, db: Annotated[Session, Depends(database_session)]) -> UserSession:
    cookie_name = request.app.state.settings.session_cookie_name
    raw_token = request.cookies.get(cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    record = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
    now = datetime.now(timezone.utc)
    if record is None or record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return record


def current_user(
    session_record: Annotated[UserSession, Depends(current_session)],
    db: Annotated[Session, Depends(database_session)],
) -> User:
    user = db.get(User, session_record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return user


def require_csrf(
    request: Request,
    session_record: Annotated[UserSession, Depends(current_session)],
) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not secrets_compare(supplied, session_record.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def secrets_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)
