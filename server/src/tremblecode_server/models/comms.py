from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class MessageStatus:
    QUEUED = "queued"
    NOTIFIED = "notified"
    DELIVERED = "delivered"
    ACKED = "acked"
    EXPIRED = "expired"


class Message(Base, PkMixin, TimestampMixin):
    """A message on the project bus. Participants are agent names or 'human'."""

    __tablename__ = "messages"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    from_participant: Mapped[str] = mapped_column(String(64))
    to_participant: Mapped[str] = mapped_column(String(64), index=True)  # or 'broadcast'
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(256), default="")
    body_md: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    ack_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(
        String(16), default=MessageStatus.QUEUED, index=True
    )
    task_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    nudge_count: Mapped[int] = mapped_column(Integer, default=0)
    # broadcast bookkeeping: who already pulled this message
    delivered_to: Mapped[list] = mapped_column(JSON, default=list)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ack_note: Mapped[str] = mapped_column(Text, default="")
    redis_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class EscalationStatus:
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class Escalation(Base, PkMixin, TimestampMixin):
    """A hot topic requiring human input."""

    __tablename__ = "escalations"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_agents.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), default="system")
    # question | destructive_op | milestone_gate | stuck_agent | mcp_approval
    type: Mapped[str] = mapped_column(String(32), default="question")
    topic: Mapped[str] = mapped_column(String(256))
    body_md: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[list] = mapped_column(JSON, default=list)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(
        String(16), default=EscalationStatus.OPEN, index=True
    )
    ref_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # milestone/msg id
    response_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
