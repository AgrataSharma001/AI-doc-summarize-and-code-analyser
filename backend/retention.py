"""Remove expired conversations and their cascading source/result rows."""

import time

from sqlalchemy import delete

from backend.models import Conversation


def purge_expired(session_factory) -> None:
    with session_factory() as session:
        session.execute(delete(Conversation).where(Conversation.expires_at <= int(time.time())))
        session.commit()
