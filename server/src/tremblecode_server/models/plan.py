from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class PlanStatus:
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Plan(Base, PkMixin, TimestampMixin):
    __tablename__ = "plans"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=PlanStatus.DRAFT)
    specs_md: Mapped[str] = mapped_column(Text, default="")
    risks_md: Mapped[str] = mapped_column(Text, default="")
    gantt_json: Mapped[list] = mapped_column(JSON, default=list)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserStory(Base, PkMixin, TimestampMixin):
    __tablename__ = "user_stories"

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    story_key: Mapped[str] = mapped_column(String(16))  # US-001
    role: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    benefit: Mapped[str] = mapped_column(Text, default="")
    acceptance_md: Mapped[str] = mapped_column(Text, default="")


class MilestoneStatus:
    PENDING = "pending"
    ACTIVE = "active"
    GATE_OPEN = "gate_open"
    APPROVED = "approved"


class Milestone(Base, PkMixin, TimestampMixin):
    __tablename__ = "milestones"

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(16))  # M1
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default=MilestoneStatus.PENDING)
