import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.common import set_chatter_members
from app.database import Base
from app.messages.presenter import message_out
from app.messages.routes import update_message
from app.models import Chatter, Message, Role, User
from app.schemas import MessageUpdate


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


def add_user(db, name, email, role_name="developer"):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name.title()} role")
        db.add(role)
        db.flush()
    user = User(name=name, login=email, email=email, hashed_password="x", roles=[role])
    db.add(user)
    db.flush()
    return user


def add_message(db, sender, other_member=None, created_at=None):
    chatter = Chatter(name="Support", created_by_id=sender.id)
    db.add(chatter)
    db.flush()
    member_ids = [sender.id]
    if other_member:
        member_ids.append(other_member.id)
    set_chatter_members(db, chatter, member_ids)
    message = Message(
        chatter_id=chatter.id,
        sender_id=sender.id,
        body="Original message",
        original_body="Original message",
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=created_at or datetime.now(timezone.utc),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def test_sender_can_edit_fresh_message(db):
    sender = add_user(db, "Sender", "sender@example.com")
    message = add_message(db, sender)

    updated = update_message(message.id, MessageUpdate(body="Updated message"), db=db, current_user=sender)

    assert updated["body"] == "Updated message"
    assert updated["can_edit"] is True
    assert updated["is_edited"] is True


def test_sender_cannot_edit_after_window_expires(db):
    sender = add_user(db, "Sender", "sender@example.com")
    old_time = datetime.now(timezone.utc) - timedelta(minutes=11)
    message = add_message(db, sender, created_at=old_time)

    with pytest.raises(HTTPException) as exc:
        update_message(message.id, MessageUpdate(body="Too late"), db=db, current_user=sender)

    assert exc.value.status_code == 403
    assert "expired" in exc.value.detail.lower()


def test_other_user_cannot_edit_message_body(db):
    sender = add_user(db, "Sender", "sender@example.com")
    other = add_user(db, "Other", "other@example.com")
    message = add_message(db, sender, other_member=other)

    with pytest.raises(HTTPException) as exc:
        update_message(message.id, MessageUpdate(body="Not mine"), db=db, current_user=other)

    assert exc.value.status_code == 403
    assert "sender" in exc.value.detail.lower()


def test_message_out_marks_expired_message_not_editable(db):
    sender = add_user(db, "Sender", "sender@example.com")
    old_time = datetime.now(timezone.utc) - timedelta(minutes=11)
    message = add_message(db, sender, created_at=old_time)

    rendered = message_out(message, sender)

    assert rendered["can_edit"] is False
    assert rendered["can_edit_until"] is not None
