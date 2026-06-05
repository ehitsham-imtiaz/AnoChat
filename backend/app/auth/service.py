from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.auth.password import verify_password
from app.database import get_db
from app.models import LoginAudit, User


bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_user(db: Session, login: str, password: str, request: Request | None = None) -> User | None:
    login_key = str(login or "").strip().lower()
    user = db.query(User).filter(
        (func.lower(User.login) == login_key) | (func.lower(User.email) == login_key)
    ).first()
    ok = bool(user and user.active and verify_password(password, user.hashed_password))
    db.add(LoginAudit(
        login=login_key,
        user_id=user.id if user else None,
        status="success" if ok else "failed",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        note=None if ok else "Invalid credentials",
    ))
    db.commit()
    return user if ok else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
        session_version = int(payload.get("sv"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or missing")
    if session_version != user.active_session_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired due to login from another device")
    return user
