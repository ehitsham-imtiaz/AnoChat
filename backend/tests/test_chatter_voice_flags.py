import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatters.routes import get_chatter
from app.common import set_chatter_members
from app.database import Base
from app.models import Chatter, Role, User
from app.schemas import ChatterOut


def test_chatter_response_exposes_voice_note_flag():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    role = Role(name="developer", description="Developer role")
    user = User(name="Voice User", login="voice@example.com", email="voice@example.com", hashed_password="x", roles=[role])
    chatter = Chatter(name="Voice Enabled", allow_voice_notes=True, allow_calls=True, allow_video_calls=False)
    db.add_all([role, user, chatter])
    db.flush()
    set_chatter_members(db, chatter, [user.id])
    db.commit()

    rendered = ChatterOut.model_validate(get_chatter(chatter.id, db=db, current_user=user))

    assert rendered.allow_voice_notes is True
    assert rendered.allow_calls is True
    assert rendered.allow_video_calls is False
