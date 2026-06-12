import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import AgentState, Project, ProjectAgent, ProjectStatus
from ..ws.manager import manager
from . import docker_service, provisioner
from .secrets import decrypt
from .settings_store import get_setting

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {ProjectStatus.PLANNING, ProjectStatus.PLAN_REVIEW, ProjectStatus.EXECUTING}


async def _allocate_port_base(session: AsyncSession) -> int:
    settings = get_settings()
    highest = await session.scalar(select(func.max(Project.port_base)))
    return (highest + settings.port_block_size) if highest else settings.port_block_start


async def _api_key(session: AsyncSession) -> str | None:
    auth = await get_setting(session, "auth")
    if auth.get("mode") == "api_key" and auth.get("anthropic_api_key_encrypted"):
        return decrypt(auth["anthropic_api_key_encrypted"])
    return None


async def start_project(session: AsyncSession, project: Project) -> Project:
    if project.status == ProjectStatus.DISCUSSION:
        raise HTTPException(409, "finalize the discussion into a PRD first")
    if not project.prd_md:
        raise HTTPException(409, "project has no PRD")

    settings = get_settings()
    if project.port_base is None:
        project.port_base = await _allocate_port_base(session)
    if project.host_dir is None:
        project.host_dir = str(settings.projects_dir / project.slug)

    specs = await provisioner.roster_for_project(session, project)
    if not any(s["kind"] == "lead" for s in specs):
        raise HTTPException(409, "roster must include a lead agent")

    await provisioner.provision_project_skeleton(project, specs)

    # Provision the lead now; workers are provisioned on plan approval.
    existing = {
        a.name: a
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project.id)
        )
    }
    for spec in specs:
        if spec["kind"] != "lead" or spec["name"] in existing:
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

    image = (
        settings.sandbox_image_flutter
        if project.image_variant == "flutter"
        else settings.sandbox_image
    )
    try:
        container_id = await docker_service.create_sandbox(
            slug=project.slug,
            image=image,
            host_dir=provisioner.project_dirs(project)["base"],
            project_id=project.id,
            port_base=project.port_base,
            api_key=await _api_key(session),
        )
    except docker_service.SandboxError as exc:
        raise HTTPException(409, str(exc)) from exc

    project.container_id = container_id
    if project.status in (ProjectStatus.DRAFT, ProjectStatus.PAUSED):
        project.status = (
            ProjectStatus.EXECUTING
            if project.config_json.get("plan_approved")
            else ProjectStatus.PLANNING
        )
    await session.commit()
    await manager.broadcast(
        "project.started", project.id, {"container_id": container_id}
    )
    return project


async def pause_project(session: AsyncSession, project: Project) -> Project:
    await docker_service.stop_sandbox(project.slug)
    project.status = ProjectStatus.PAUSED
    for agent in await session.scalars(
        select(ProjectAgent).where(ProjectAgent.project_id == project.id)
    ):
        agent.state = AgentState.STOPPED
    await session.commit()
    await manager.broadcast("project.paused", project.id, {})
    return project


async def resume_project(session: AsyncSession, project: Project) -> Project:
    if project.status != ProjectStatus.PAUSED:
        raise HTTPException(409, "project is not paused")
    # pause flipped agents to STOPPED; the relay skips stopped agents, so they
    # must be revived or no tmux sessions are launched after the container starts
    for agent in await session.scalars(
        select(ProjectAgent).where(ProjectAgent.project_id == project.id)
    ):
        if agent.state == AgentState.STOPPED and agent.workspace_path:
            agent.state = AgentState.STARTING
    status = await docker_service.sandbox_status(project.slug)
    if status is None:
        return await start_project(session, project)
    if status != "running":
        await docker_service.start_sandbox(project.slug)
    project.status = (
        ProjectStatus.EXECUTING
        if project.config_json.get("plan_approved")
        else ProjectStatus.PLANNING
    )
    await session.commit()
    await manager.broadcast("project.resumed", project.id, {})
    return project


async def reconcile_on_boot(session: AsyncSession) -> None:
    """Keep sandboxes consistent with DB state across server restarts."""
    projects = await session.scalars(
        select(Project).where(Project.container_id.is_not(None))
    )
    for project in projects:
        if project.status not in ACTIVE_STATUSES:
            continue
        try:
            status = await docker_service.sandbox_status(project.slug)
            if status == "running":
                continue
            if status is None:
                logger.warning(
                    "sandbox for %s missing — recreating", project.slug
                )
                await start_project(session, project)
            else:
                await docker_service.start_sandbox(project.slug)
        except Exception:
            logger.exception("reconcile failed for project %s", project.slug)
