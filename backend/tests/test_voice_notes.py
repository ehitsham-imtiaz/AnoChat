import sys
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.attachments.routes import upload_attachment
from app.common import set_chatter_members
from app.database import Base
from app.models import Chatter, Role, User


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("app.attachments.routes.settings.upload_dir", tmp_path)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def add_user(db, name, email):
    role = Role(name="developer", description="Developer role")
    db.add(role)
    db.flush()
    user = User(name=name, login=email, email=email, hashed_password="x", roles=[role])
    db.add(user)
    db.flush()
    return user


@pytest.mark.anyio
async def test_audio_upload_stores_duration(db):
    user = add_user(db, "Sender", "sender@example.com")
    chatter = Chatter(name="Voice", created_by_id=user.id)
    db.add(chatter)
    db.flush()
    set_chatter_members(db, chatter, [user.id])
    db.commit()
    source = Path(__file__).resolve().parent / "voice-note.webm"
    source.write_bytes(b"fake audio content")
    try:
        with source.open("rb") as handle:
            upload = UploadFile(file=handle, filename="voice-note.webm")
            upload.headers = {"content-type": "audio/webm;codecs=opus"}
            saved = await upload_attachment(
                file=upload,
                project_id=None,
                chatter_id=chatter.id,
                duration_seconds=3.4,
                db=db,
                current_user=user,
            )
    finally:
        source.unlink(missing_ok=True)

    assert saved.content_type == "audio/webm"
    assert saved.duration_seconds == 3.4
