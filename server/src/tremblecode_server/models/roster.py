from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import PkMixin, TimestampMixin


class AgentTemplate(Base, PkMixin, TimestampMixin):
    """A configurable agent 'figure' (role template) usable across projects."""

    __tablename__ = "agent_templates"

    role_key: Mapped[str] = mapped_column(String(64), unique=True)  # e.g. backend_dev
    display_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt_md: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64), default="sonnet")
    # thinking effort passed to `claude --effort`: low|medium|high|xhigh
    effort: Mapped[str] = mapped_column(String(16), default="medium")
    default_count: Mapped[int] = mapped_column(Integer, default=1)
    color: Mapped[str] = mapped_column(String(16), default="#33ff57")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # lead | dev | qa — drives tool gating and workflow routing
    kind: Mapped[str] = mapped_column(String(16), default="dev")
