from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import Project, ProjectAgent
from ..schemas.core import ProjectAgentOut
from ..services import agent_service, docker_service
from .deps import SessionDep

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/projects/{project_id}/agents", response_model=list[ProjectAgentOut])
async def list_agents(project_id: str, session: SessionDep):
    rows = await session.scalars(
        select(ProjectAgent).where(ProjectAgent.project_id == project_id)
    )
    return list(rows)


class AgentAddIn(BaseModel):
    role_key: str
    model: str | None = None
    effort: str | None = None


@router.post("/projects/{project_id}/agents", response_model=ProjectAgentOut, status_code=201)
async def add_agent(project_id: str, payload: AgentAddIn, session: SessionDep):
    """Add an agent to a running project. The in-container relay launches its
    session within ~10s — no container restart."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return await agent_service.add_agent(
        session, project, payload.role_key, payload.model, payload.effort
    )


async def _agent_and_project(session, agent_id: str) -> tuple[ProjectAgent, Project]:
    agent = await session.get(ProjectAgent, agent_id)
    if not agent:
        raise HTTPException(404, "agent not found")
    project = await session.get(Project, agent.project_id)
    return agent, project


@router.post("/agents/{agent_id}/restart")
async def restart_agent(agent_id: str, session: SessionDep):
    """Kill the agent's tmux session; the in-container reconciler relaunches
    it with --continue (conversation preserved)."""
    agent, project = await _agent_and_project(session, agent_id)
    code, out = await docker_service.exec_in_sandbox(
        project.slug, ["tmux", "kill-session", "-t", f"={agent.tmux_session}"]
    )
    if code != 0 and "can't find session" not in out:
        raise HTTPException(502, f"tmux kill failed: {out}")
    return {"ok": True}


@router.post("/agents/{agent_id}/interrupt")
async def interrupt_agent(agent_id: str, session: SessionDep):
    """Send Escape to the agent's pane (interrupts the current turn)."""
    agent, project = await _agent_and_project(session, agent_id)
    code, out = await docker_service.exec_in_sandbox(
        project.slug,
        ["tmux", "send-keys", "-t", f"={agent.tmux_session}:0.0", "Escape"],
    )
    if code != 0:
        raise HTTPException(502, f"tmux interrupt failed: {out}")
    return {"ok": True}
