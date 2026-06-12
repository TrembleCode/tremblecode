from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class TaskStatus:
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    MERGING = "MERGING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class Task(Base, PkMixin, TimestampMixin):
    __tablename__ = "tasks"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    milestone_id: Mapped[str | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    task_key: Mapped[str] = mapped_column(String(16))  # T-001
    title: Mapped[str] = mapped_column(String(256))
    description_md: Mapped[str] = mapped_column(Text, default="")
    role_key: Mapped[str] = mapped_column(String(64))  # which agent figure handles it
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.PENDING, index=True)
    assignee_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_agents.id", ondelete="SET NULL"), nullable=True
    )
    review_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_agents.id", ondelete="SET NULL"), nullable=True
    )
    branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)  # task_keys
    estimate_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TaskEvent(Base, PkMixin, TimestampMixin):
    __tablename__ = "task_events"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(String(64))  # agent name or "human"/"system"
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
