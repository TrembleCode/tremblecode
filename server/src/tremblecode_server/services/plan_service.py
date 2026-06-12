import logging
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AgentState,
    Milestone,
    MilestoneStatus,
    Plan,
    PlanStatus,
    Project,
    ProjectAgent,
    ProjectStatus,
    Task,
    TaskStatus,
    UserStory,
    McpSuggestion,
)
from ..schemas.plan import PlanPackageIn
from ..ws.manager import manager
from . import bus, message_service, provisioner
from .mcp_catalog import catalog_entry

logger = logging.getLogger(__name__)


def validate_plan(
    package: dict, roster_role_keys: set[str]
) -> tuple[PlanPackageIn | None, list[str]]:
    try:
        plan = PlanPackageIn.model_validate(package)
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        ]

    errors: list[str] = []
    if not plan.milestones:
        errors.append("at least one milestone is required")
    if not plan.tasks:
        errors.append("at least one task is required")

    milestone_keys = {m.key for m in plan.milestones}
    if len(milestone_keys) != len(plan.milestones):
        errors.append("milestone keys must be unique")
    task_keys = {t.task_key for t in plan.tasks}
    if len(task_keys) != len(plan.tasks):
        errors.append("task keys must be unique")

    workers = roster_role_keys - {"team_lead"}
    for task in plan.tasks:
        if task.milestone_key not in milestone_keys:
            errors.append(f"{task.task_key}: unknown milestone '{task.milestone_key}'")
        if task.role_key not in workers:
            errors.append(
                f"{task.task_key}: role_key '{task.role_key}' is not a worker role "
                f"on this team (available: {sorted(workers)})"
            )
        for dep in task.dependencies:
            if dep not in task_keys:
                errors.append(f"{task.task_key}: unknown dependency '{dep}'")
            if dep == task.task_key:
                errors.append(f"{task.task_key}: depends on itself")
    return (plan if not errors else None), errors


async def submit_plan(
    session: AsyncSession, project: Project, package: dict
) -> tuple[Plan | None, list[str]]:
    roster = {entry["role_key"] for entry in project.config_json.get("roster", [])}
    plan_in, errors = validate_plan(package, roster)
    if plan_in is None:
        return None, errors

    # replace any previous draft
    old = list(
        await session.scalars(
            select(Plan).where(
                Plan.project_id == project.id, Plan.status == PlanStatus.DRAFT
            )
        )
    )
    version = 1 + max(
        [p.version for p in await session.scalars(select(Plan).where(Plan.project_id == project.id))],
        default=0,
    )
    for plan in old:
        await session.delete(plan)

    plan = Plan(
        project_id=project.id,
        version=version,
        specs_md=plan_in.specs_md,
        risks_md=plan_in.risks_md,
        raw_json=package,
    )
    session.add(plan)
    await session.flush()

    for story in plan_in.user_stories:
        session.add(UserStory(plan_id=plan.id, **story.model_dump()))

    milestones_by_key: dict[str, Milestone] = {}
    for i, milestone_in in enumerate(plan_in.milestones):
        milestone = Milestone(
            plan_id=plan.id,
            project_id=project.id,
            key=milestone_in.key,
            name=milestone_in.name,
            description=milestone_in.description,
            sort=i,
        )
        session.add(milestone)
        milestones_by_key[milestone_in.key] = milestone
    await session.flush()

    # tasks are created on approval-time copy? No — create now, replace on resubmit
    old_tasks = await session.scalars(
        select(Task).where(Task.project_id == project.id, Task.status == TaskStatus.PENDING)
    )
    for task in old_tasks:
        await session.delete(task)
    for task_in in plan_in.tasks:
        session.add(
            Task(
                project_id=project.id,
                plan_id=plan.id,
                milestone_id=milestones_by_key[task_in.milestone_key].id,
                task_key=task_in.task_key,
                title=task_in.title,
                description_md=task_in.description_md,
                role_key=task_in.role_key,
                dependencies=task_in.dependencies,
                estimate_h=task_in.estimate_h,
            )
        )

    for suggestion in plan_in.mcp_suggestions:
        entry = catalog_entry(suggestion.name)
        if entry is None:
            continue
        session.add(
            McpSuggestion(
                project_id=project.id,
                name=suggestion.name,
                transport=entry.get("transport", "stdio"),
                command=entry.get("command", ""),
                args=entry.get("args", []),
                env_keys=entry.get("env_keys", []),
                reason=suggestion.reason,
            )
        )

    project.status = ProjectStatus.PLAN_REVIEW
    await session.commit()
    await manager.broadcast("plan.submitted", project.id, {"version": version})
    return plan, []


async def approve_plan(session: AsyncSession, project: Project, plan: Plan) -> None:
    plan.status = PlanStatus.APPROVED
    plan.approved_at = datetime.now(timezone.utc)
    project.status = ProjectStatus.EXECUTING
    project.config_json = {**project.config_json, "plan_approved": True}

    # provision worker agents (lead already exists)
    existing = {
        a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project.id)
        )
    }
    specs = await provisioner.roster_for_project(session, project)
    for spec in specs:
        if spec["kind"] == "lead" or spec["name"] in existing:
            continue
        agent = ProjectAgent(
            project_id=project.id,
            template_id=spec["template_id"],
            name=spec["name"],
            role_key=spec["role_key"],
            kind=spec["kind"],
            model=spec["model"],
            effort=spec["effort"],
            state=AgentState.STARTING,
            tmux_session=f"tc-{spec['name']}",
        )
        workspace = await provisioner.provision_agent_workspace(project, agent, spec)
        agent.workspace_path = str(workspace)
        session.add(agent)

    # activate the first milestone
    first = await session.scalar(
        select(Milestone)
        .where(Milestone.plan_id == plan.id)
        .order_by(Milestone.sort)
        .limit(1)
    )
    if first:
        first.status = MilestoneStatus.ACTIVE

    # planning is done — drop the lead to medium effort and give it a fresh
    # context. Stream order matters: set_effort → clear → message doorbell,
    # so the relay applies /effort and /clear before the approval message
    # lands on the fresh session.
    lead_agent = await session.scalar(
        select(ProjectAgent).where(
            ProjectAgent.project_id == project.id, ProjectAgent.kind == "lead"
        )
    )
    if lead_agent:
        lead_agent.effort = "medium"
    await session.commit()

    if lead_agent:
        try:
            await bus.publish(
                project.id,
                {
                    "type": "set_effort",
                    "to": lead_agent.name,
                    "level": "medium",
                    "reason": "planning done",
                },
            )
            await bus.publish(
                project.id,
                {"type": "clear", "to": lead_agent.name, "reason": "plan approved"},
            )
        except Exception:
            logger.exception("set_effort/clear publish failed")

    await message_service.create_message(
        session,
        project_id=project.id,
        from_participant="human",
        to_participant="lead",
        subject="Plan approved",
        body_md=(
            f"Your plan (v{plan.version}) is APPROVED. Milestone "
            f"{first.key if first else '?'} is active. Worker agents are being "
            "provisioned — check get_team, then assign the dependency-free tasks "
            "with assign_task. The server sends each assignee a brief pointer "
            "automatically — do NOT send separate brief messages."
        ),
        ack_requested=True,
    )
    await manager.broadcast("plan.approved", project.id, {"version": plan.version})


async def reject_plan(
    session: AsyncSession, project: Project, plan: Plan, comments: str
) -> None:
    plan.status = PlanStatus.REJECTED
    project.status = ProjectStatus.PLANNING
    await session.commit()
    await message_service.create_message(
        session,
        project_id=project.id,
        from_participant="human",
        to_participant="lead",
        subject="Plan rejected — revise and resubmit",
        body_md=f"The plan was rejected. Address these comments and submit a "
        f"revised plan via submit_plan:\n\n{comments}",
        ack_requested=True,
    )
    await manager.broadcast("plan.rejected", project.id, {"version": plan.version})
