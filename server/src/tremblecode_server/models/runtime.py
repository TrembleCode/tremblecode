from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class McpSuggestion(Base, PkMixin, TimestampMixin):
    __tablename__ = "mcp_suggestions"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    transport: Mapped[str] = mapped_column(String(16), default="stdio")
    command: Mapped[str] = mapped_column(String(256), default="")
    args: Mapped[list] = mapped_column(JSON, default=list)
    env_keys: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")
    # proposed | approved | rejected | installed
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    env_values_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentRequest(Base, PkMixin, TimestampMixin):
    """A lead-initiated request to grow the team, pending human approval."""

    __tablename__ = "agent_requests"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[str] = mapped_column(String(64), default="lead")
    role_key: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text, default="")
    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(16), default="pending")


class AgentSession(Base, PkMixin, TimestampMixin):
    __tablename__ = "agent_sessions"

    agent_id: Mapped[str] = mapped_column(
        ForeignKey("project_agents.id", ondelete="CASCADE"), index=True
    )
    claude_session_id: Mapped[str] = mapped_column(String(64), index=True)
    transcript_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # clear | compact_restart | crash | mcp_reload | stop
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CostEvent(Base, PkMixin, TimestampMixin):
    __tablename__ = "cost_events"
    __table_args__ = (
        UniqueConstraint("claude_session_id", "transcript_offset", name="uq_cost_dedup"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("project_agents.id", ondelete="CASCADE"), index=True
    )
    claude_session_id: Mapped[str] = mapped_column(String(64))
    transcript_offset: Mapped[int] = mapped_column(Integer)  # dedup key
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class AgentEvent(Base, PkMixin, TimestampMixin):
    """Hook firehose from in-container Claude Code sessions."""

    __tablename__ = "agent_events"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_agents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), default="")
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Service(Base, PkMixin, TimestampMixin):
    """A dev server registered by an agent inside the sandbox."""

    __tablename__ = "services"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    agent_name: Mapped[str] = mapped_column(String(64), default="")
    container_port: Mapped[int] = mapped_column(Integer)
    host_port: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="up")  # up|down
