from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class Discussion(Base, PkMixin, TimestampMixin):
    """Pre-PRD project creation interview with a planning agent."""

    __tablename__ = "discussions"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    claude_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|finalized


class DiscussionMessage(Base, PkMixin, TimestampMixin):
    __tablename__ = "discussion_messages"

    discussion_id: Mapped[str] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
