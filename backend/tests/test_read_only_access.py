import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatters.routes import create_message
from app.common import set_chatter_members
from app.database import Base
from app.models import Chatter, Role, User
from app.projects.routes import create_project
from app.schemas import MessageCreate, ProjectCreate


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


def add_user(db, name, email, role_name="developer", read_only=False):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name.title()} role")
        db.add(role)
        db.flush()
    user = User(name=name, login=email, email=email, hashed_password="x", read_only=read_only, roles=[role])
    db.add(user)
    db.flush()
    return user


def test_global_read_only_admin_cannot_create_project(db):
    admin = add_user(db, "Admin User", "admin@example.com", "admin", read_only=True)
    payload = ProjectCreate(name="Read Only Test")

    with pytest.raises(HTTPException) as exc:
        create_project(payload, db=db, current_user=admin)

    assert exc.value.status_code == 403


def test_project_read_only_member_ids_are_returned(db):
    admin = add_user(db, "Admin User", "admin@example.com", "admin")
    member = add_user(db, "Member User", "member@example.com")
    payload = ProjectCreate(name="Website", member_ids=[member.id], read_only_member_ids=[member.id])

    project = create_project(payload, db=db, current_user=admin)

    assert project.read_only_member_ids == [member.id]


def test_read_only_chatter_member_cannot_send_message(db):
    admin = add_user(db, "Admin User", "admin@example.com", "admin")
    member = add_user(db, "Member User", "member@example.com")
    chatter = Chatter(name="Support", created_by_id=admin.id)
    db.add(chatter)
    db.flush()
    set_chatter_members(db, chatter, [admin.id, member.id], [member.id])
    db.commit()
    db.refresh(chatter)

    with pytest.raises(HTTPException) as exc:
        create_message(chatter.id, MessageCreate(body="Can I post?"), db=db, current_user=member)

    assert exc.value.status_code == 403
