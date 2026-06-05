import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatters.routes import list_typing, update_typing
from app.common import set_chatter_members
from app.database import Base
from app.models import Chatter, Role, User
from app.schemas import TypingStateUpdate


def test_typing_state_visible_to_other_members_and_clearable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    role = Role(name="developer", description="Developer role")
    typer = User(name="Typing User", login="typing@example.com", email="typing@example.com", hashed_password="x", roles=[role])
    viewer = User(name="Viewer User", login="viewer@example.com", email="viewer@example.com", hashed_password="x", roles=[role])
    chatter = Chatter(name="Typing Test")
    db.add_all([role, typer, viewer, chatter])
    db.flush()
    set_chatter_members(db, chatter, [typer.id, viewer.id])
    db.commit()

    update_typing(chatter.id, TypingStateUpdate(is_typing=True), db=db, current_user=typer)
    visible = list_typing(chatter.id, db=db, current_user=viewer)
    hidden_from_self = list_typing(chatter.id, db=db, current_user=typer)

    assert [user.id for user in visible] == [typer.id]
    assert hidden_from_self == []

    update_typing(chatter.id, TypingStateUpdate(is_typing=False), db=db, current_user=typer)
    assert list_typing(chatter.id, db=db, current_user=viewer) == []
