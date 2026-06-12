from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import PkMixin, TimestampMixin


class ProjectStatus:
    DISCUSSION = "DISCUSSION"
    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    PLAN_REVIEW = "PLAN_REVIEW"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Project(Base, PkMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.DISCUSSION)
    prd_md: Mapped[str] = mapped_column(Text, default="")
    host_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_variant: Mapped[str] = mapped_column(String(32), default="base")
    port_base: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # roster: [{role_key, count, model?}], ports: {name: container_port}, etc.
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    agents: Mapped[list["ProjectAgent"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class AgentState:
    PROVISIONING = "provisioning"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    WAITING_HUMAN = "waiting_human"
    STOPPED = "stopped"
    ERROR = "error"


class ProjectAgent(Base, PkMixin, TimestampMixin):
    __tablename__ = "project_agents"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_templates.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(64))  # lead, be-1, fe-1, qa-1
    role_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="dev")  # lead|dev|qa
    model: Mapped[str] = mapped_column(String(64), default="sonnet")
    # thinking effort for `claude --effort`; the lead drops high→medium after
    # plan approval (relay injects /effort)
    effort: Mapped[str] = mapped_column(String(16), default="medium")
    workspace_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tmux_session: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claude_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default=AgentState.PROVISIONING)
    current_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="agents")

    __table_args__ = ()
