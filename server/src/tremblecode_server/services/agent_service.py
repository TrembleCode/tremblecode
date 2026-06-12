"""Mid-project team growth. New ProjectAgent rows with provisioned
workspaces are picked up by the in-container relay's reconciler within ~10s —
no container restart, no disruption to running agents."""

import logging
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentState, AgentTemplate, Project, ProjectAgent
from ..ws.manager import manager
from . import provisioner

logger = logging.getLogger(__name__)

SHORT_NAMES = {"team_lead": "lead", "backend_dev": "be", "frontend_dev": "fe", "qa": "qa"}


def _next_name(role_key: str, kind: str, existing: set[str]) -> str:
    if kind == "lead":
        return "lead"
    prefix = SHORT_NAMES.get(role_key) or role_key.replace("_", "-")
    taken = {
        int(m.group(1))
        for name in existing
        if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", name))
    }
    n = 1
    while n in taken:
        n += 1
    return f"{prefix}-{n}"


async def add_agent(
    session: AsyncSession,
    project: Project,
    role_key: str,
    model: str | None = None,
    effort: str | None = None,
) -> ProjectAgent:
    template = await session.scalar(
        select(AgentTemplate).where(AgentTemplate.role_key == role_key)
    )
    if not template:
        raise HTTPException(404, f"no agent template for role '{role_key}'")
    if not project.host_dir:
        raise HTTPException(409, "project has not been started yet")

    existing = {
        a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project.id)
        )
    }
    if template.kind == "lead" and "lead" in existing:
        raise HTTPException(409, "the team already has a lead")

    name = _next_name(role_key, template.kind, existing)
    spec = {
        "name": name,
        "role_key": template.role_key,
        "kind": template.kind,
        "model": model or template.model,
        "effort": effort or template.effort,
        "display_name": template.display_name,
        "description": template.description,
        "system_prompt_md": template.system_prompt_md,
        "template_id": template.id,
    }
    agent = ProjectAgent(
        project_id=project.id,
        template_id=template.id,
        name=name,
        role_key=template.role_key,
        kind=template.kind,
        model=spec["model"],
        effort=spec["effort"],
        state=AgentState.STARTING,
        tmux_session=f"tc-{name}",
    )
    workspace = await provisioner.provision_agent_workspace(project, agent, spec)
    agent.workspace_path = str(workspace)
    session.add(agent)

    # keep the roster consistent for any future re-provisioning pass
    roster = [dict(entry) for entry in project.config_json.get("roster", [])]
    for entry in roster:
        if entry["role_key"] == role_key:
            entry["count"] = entry.get("count", 0) + 1
            break
    else:
        roster.append({"role_key": role_key, "count": 1, "model": model})
    project.config_json = {**project.config_json, "roster": roster}

    await session.commit()
    await manager.broadcast(
        "agent.added", project.id, {"name": name, "role_key": role_key}
    )
    logger.info("added agent %s (%s) to project %s", name, role_key, project.slug)
    return agent
