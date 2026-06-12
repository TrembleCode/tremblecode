from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Agent templates ──────────────────────────────────────────────


class AgentTemplateCreate(BaseModel):
    role_key: str
    display_name: str
    description: str = ""
    system_prompt_md: str
    model: str = "sonnet"
    default_count: int = 1
    color: str = "#33ff57"
    kind: str = "dev"  # lead | dev | qa


class AgentTemplateUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    system_prompt_md: str | None = None
    model: str | None = None
    default_count: int | None = None
    color: str | None = None
    kind: str | None = None


class AgentTemplateOut(OrmModel):
    id: str
    role_key: str
    display_name: str
    description: str
    system_prompt_md: str
    model: str
    default_count: int
    color: str
    kind: str
    is_builtin: bool


# ── Projects ─────────────────────────────────────────────────────


class RosterEntry(BaseModel):
    role_key: str
    count: int = 1
    model: str | None = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    prd_md: str = ""
    roster: list[RosterEntry] = Field(default_factory=list)
    image_variant: str = "base"
    start_with_discussion: bool = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    config_json: dict | None = None


class ProjectAgentOut(OrmModel):
    id: str
    name: str
    role_key: str
    kind: str
    model: str
    state: str
    current_task_id: str | None
    workspace_path: str | None
    last_activity_at: datetime | None


class ProjectOut(OrmModel):
    id: str
    name: str
    slug: str
    description: str
    status: str
    prd_md: str
    host_dir: str | None
    container_id: str | None
    image_variant: str
    port_base: int | None
    config_json: dict
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    agents: list[ProjectAgentOut] = Field(default_factory=list)


class PrdUpdate(BaseModel):
    prd_md: str
