from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import (
    Milestone,
    Plan,
    PlanStatus,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
    UserStory,
)
from ..schemas.core import OrmModel
from ..services import message_service, plan_service
from ..services.mcp_catalog import catalog_for_prompt
from .deps import SessionDep

router = APIRouter(prefix="/api", tags=["plans"])


class StoryOut(OrmModel):
    id: str
    story_key: str
    role: str
    action: str
    benefit: str
    acceptance_md: str


class MilestoneOut(OrmModel):
    id: str
    key: str
    name: str
    description: str
    sort: int
    status: str


class TaskOut(OrmModel):
    id: str
    task_key: str
    title: str
    description_md: str
    role_key: str
    status: str
    milestone_id: str | None
    assignee_agent_id: str | None
    branch: str | None
    dependencies: list
    estimate_h: float | None
    blocked_reason: str | None
    created_at: datetime
    updated_at: datetime


class PlanOut(OrmModel):
    id: str
    project_id: str
    version: int
    status: str
    specs_md: str
    risks_md: str
    created_at: datetime
    approved_at: datetime | None


class PlanDetailOut(PlanOut):
    user_stories: list[StoryOut]
    milestones: list[MilestoneOut]
    tasks: list[TaskOut]


async def _latest_plan(session, project_id: str) -> Plan | None:
    return await session.scalar(
        select(Plan)
        .where(Plan.project_id == project_id)
        .order_by(Plan.version.desc())
        .limit(1)
    )


@router.get("/projects/{project_id}/plan", response_model=PlanDetailOut)
async def get_plan(project_id: str, session: SessionDep):
    plan = await _latest_plan(session, project_id)
    if not plan:
        raise HTTPException(404, "no plan yet")
    stories = list(
        await session.scalars(select(UserStory).where(UserStory.plan_id == plan.id))
    )
    milestones = list(
        await session.scalars(
            select(Milestone).where(Milestone.plan_id == plan.id).order_by(Milestone.sort)
        )
    )
    tasks = list(
        await session.scalars(
            select(Task).where(Task.plan_id == plan.id).order_by(Task.task_key)
        )
    )
    return PlanDetailOut(
        **PlanOut.model_validate(plan).model_dump(),
        user_stories=[StoryOut.model_validate(s) for s in stories],
        milestones=[MilestoneOut.model_validate(m) for m in milestones],
        tasks=[TaskOut.model_validate(t) for t in tasks],
    )


PLANNING_BRIEF = """Begin planning now.

1. Read PRD.md in your workspace and explore any existing code.
2. Decompose the work into milestones (each independently demoable), user
   stories, and tasks sized for one agent (≤ ~4h, concrete acceptance criteria
   in description_md, explicit dependencies, role_key matching a worker figure
   on your team — check get_team).
3. Consider which MCP servers would help the team and include them as
   mcp_suggestions. Catalog:
{catalog}
4. Submit with the submit_plan tool. Fix any validation errors and resubmit.
The human reviews your plan in the dashboard; you'll be notified of the
decision. Do not start implementation before approval."""


@router.post("/projects/{project_id}/plan/generate")
async def generate_plan(project_id: str, session: SessionDep):
    """Kick the lead into planning mode (container must be running)."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    if not project.container_id:
        raise HTTPException(409, "start the project first")
    project.status = ProjectStatus.PLANNING
    await session.commit()
    await message_service.create_message(
        session,
        project_id=project_id,
        from_participant="human",
        to_participant="lead",
        subject="Generate the project plan",
        body_md=PLANNING_BRIEF.format(catalog=catalog_for_prompt()),
        ack_requested=True,
    )
    return {"ok": True}


class PlanPatch(BaseModel):
    specs_md: str | None = None
    risks_md: str | None = None


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def patch_plan(plan_id: str, payload: PlanPatch, session: SessionDep):
    plan = await session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(409, "only draft plans can be edited")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await session.commit()
    return plan


class TaskPatch(BaseModel):
    title: str | None = None
    description_md: str | None = None
    role_key: str | None = None
    estimate_h: float | None = None
    dependencies: list[str] | None = None


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def patch_task(task_id: str, payload: TaskPatch, session: SessionDep):
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if task.status != TaskStatus.PENDING:
        raise HTTPException(409, "only pending tasks can be edited")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    await session.commit()
    return task


@router.post("/plans/{plan_id}/approve", response_model=PlanOut)
async def approve_plan(plan_id: str, session: SessionDep):
    plan = await session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(409, f"plan is {plan.status}")
    project = await session.get(Project, plan.project_id)
    await plan_service.approve_plan(session, project, plan)
    return plan


class RejectIn(BaseModel):
    comments: str


@router.post("/plans/{plan_id}/reject", response_model=PlanOut)
async def reject_plan(plan_id: str, payload: RejectIn, session: SessionDep):
    plan = await session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(409, f"plan is {plan.status}")
    project = await session.get(Project, plan.project_id)
    await plan_service.reject_plan(session, project, plan, payload.comments)
    return plan
