from pydantic import BaseModel, Field


class PlanStoryIn(BaseModel):
    story_key: str
    role: str
    action: str
    benefit: str = ""
    acceptance_md: str = ""


class PlanMilestoneIn(BaseModel):
    key: str
    name: str
    description: str = ""


class PlanTaskIn(BaseModel):
    task_key: str
    title: str
    description_md: str
    role_key: str
    milestone_key: str
    dependencies: list[str] = Field(default_factory=list)
    estimate_h: float | None = None


class McpSuggestionIn(BaseModel):
    name: str
    reason: str = ""


class PlanPackageIn(BaseModel):
    specs_md: str
    risks_md: str = ""
    user_stories: list[PlanStoryIn] = Field(default_factory=list)
    milestones: list[PlanMilestoneIn]
    tasks: list[PlanTaskIn]
    mcp_suggestions: list[McpSuggestionIn] = Field(default_factory=list)
