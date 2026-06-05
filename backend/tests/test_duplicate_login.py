import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.password import hash_password
from app.auth.routes import login
from app.auth.service import get_current_user
from app.database import Base
from app.models import Role, User
from app.schemas import LoginRequest


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def add_user(db):
    role = Role(name="admin", description="Admin role")
    user = User(
        name="Admin User",
        login="admin@example.com",
        email="admin@example.com",
        hashed_password=hash_password("Admin123!"),
        roles=[role],
    )
    db.add_all([role, user])
    db.commit()
    db.refresh(user)
    return user


def bearer(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_second_login_invalidates_previous_token(db):
    user = add_user(db)
    payload = LoginRequest(login=user.email, password="Admin123!")

    first = login(payload, None, db)
    second = login(payload, None, db)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=bearer(first.access_token), db=db)
    assert exc.value.status_code == 401
    assert "another device" in exc.value.detail

    current = get_current_user(credentials=bearer(second.access_token), db=db)
    assert current.id == user.id
