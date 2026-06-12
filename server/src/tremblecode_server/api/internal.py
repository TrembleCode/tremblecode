"""Container-only endpoints, authenticated by the shared internal secret.

The in-container relay pulls desired agent state from here and pushes hook
events, messages, costs and status updates back.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import (
    AgentEvent,
    AgentSession,
    AgentState,
    McpSuggestion,
    Message,
    Milestone,
    Project,
    ProjectAgent,
    Service,
    Task,
    TaskStatus,
)
from ..services import (
    escalation_service,
    message_service,
    plan_service,
    task_service,
)
from ..ws.manager import manager
from .deps import SessionDep, require_internal_secret

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_secret)],
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _agent_or_404(
    session, project_id: str, agent_name: str
) -> ProjectAgent:
    agent = await session.scalar(
        select(ProjectAgent).where(
            ProjectAgent.project_id == project_id, ProjectAgent.name == agent_name
        )
    )
    if not agent:
        raise HTTPException(404, f"agent '{agent_name}' not found")
    return agent


# ── Desired state (relay reconciler) ─────────────────────────────


@router.get("/projects/{project_id}/agents")
async def desired_agents(project_id: str, session: SessionDep):
    """The relay reconciles tmux sessions against this list."""
    import json as jsonlib

    from ..services.secrets import decrypt

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    agents = await session.scalars(
        select(ProjectAgent).where(ProjectAgent.project_id == project_id)
    )
    # secrets for approved MCP servers ride the internal channel and land in
    # the tmux session env (never in committed files)
    extra_env: dict[str, str] = {}
    for suggestion in await session.scalars(
        select(McpSuggestion).where(
            McpSuggestion.project_id == project_id,
            McpSuggestion.status == "installed",
        )
    ):
        if suggestion.env_values_encrypted:
            try:
                extra_env.update(
                    jsonlib.loads(decrypt(suggestion.env_values_encrypted))
                )
            except Exception:
                pass
    return {
        "project_status": project.status,
        "extra_env": extra_env,
        "agents": [
            {
                "name": a.name,
                "role_key": a.role_key,
                "kind": a.kind,
                "model": a.model,
                "effort": a.effort,
                "state": a.state,
                "workspace": a.workspace_path,
                "tmux_session": a.tmux_session,
                "identity_path": (
                    f"{project.host_dir}/.tremblecode/agents/{a.name}/identity.md"
                ),
            }
            for a in agents
        ],
    }


# ── Hook firehose ────────────────────────────────────────────────

HOOK_STATE_TRANSITIONS = {
    "busy": AgentState.BUSY,
    "heartbeat": AgentState.BUSY,
    "stop": AgentState.IDLE,
    "session-start": AgentState.IDLE,
}


class HookIn(BaseModel):
    agent: str
    event: str  # session-start | busy | heartbeat | stop | pre-compact | ...
    payload: dict = {}


@router.post("/projects/{project_id}/hooks")
async def ingest_hook(project_id: str, body: HookIn, session: SessionDep):
    agent = await _agent_or_404(session, project_id, body.agent)

    # Don't store heartbeats (too chatty); they only refresh state.
    if body.event != "heartbeat":
        session.add(
            AgentEvent(
                project_id=project_id,
                agent_id=agent.id,
                agent_name=agent.name,
                event=body.event,
                payload={
                    k: v
                    for k, v in body.payload.items()
                    if k in ("session_id", "source", "trigger", "tool_name", "message")
                },
            )
        )

    new_state = HOOK_STATE_TRANSITIONS.get(body.event)
    state_changed = new_state is not None and agent.state not in (
        AgentState.STOPPED,
        AgentState.PROVISIONING,
    ) and agent.state != new_state
    if new_state and agent.state not in (AgentState.STOPPED,):
        agent.state = new_state
    agent.last_activity_at = _now()

    session_id = body.payload.get("session_id")
    if body.event == "session-start" and session_id:
        if agent.claude_session_id != session_id:
            agent.claude_session_id = session_id
            session.add(
                AgentSession(
                    agent_id=agent.id,
                    claude_session_id=session_id,
                    transcript_path=body.payload.get("transcript_path"),
                    started_at=_now(),
                )
            )
    await session.commit()

    if state_changed:
        await manager.broadcast(
            "agent.state",
            project_id,
            {"agent": agent.name, "state": agent.state},
        )
    return {"ok": True}


# ── Agent status (report_status tool) ────────────────────────────


class StatusIn(BaseModel):
    agent: str
    state: str  # working | idle | blocked | waiting
    detail: str = ""


@router.post("/projects/{project_id}/status")
async def report_status(project_id: str, body: StatusIn, session: SessionDep):
    agent = await _agent_or_404(session, project_id, body.agent)
    mapped = {
        "working": AgentState.BUSY,
        "idle": AgentState.IDLE,
        "blocked": AgentState.WAITING_HUMAN,
        "waiting": AgentState.IDLE,
    }.get(body.state)
    if mapped:
        agent.state = mapped
    agent.last_activity_at = _now()
    await session.commit()
    await manager.broadcast(
        "agent.state",
        project_id,
        {"agent": agent.name, "state": agent.state, "detail": body.detail},
    )
    return {"ok": True}


# ── Messages (MCP tools route through the relay to here) ─────────


class InternalMessageCreate(BaseModel):
    from_agent: str
    to: str
    body_md: str
    subject: str = ""
    thread_id: str | None = None
    ack_requested: bool = False
    priority: str = "normal"
    task_key: str | None = None


@router.post("/projects/{project_id}/messages")
async def internal_send_message(
    project_id: str, body: InternalMessageCreate, session: SessionDep
):
    message = await message_service.create_message(
        session,
        project_id=project_id,
        from_participant=body.from_agent,
        to_participant=body.to,
        body_md=body.body_md,
        subject=body.subject,
        thread_id=body.thread_id,
        ack_requested=body.ack_requested,
        priority=body.priority,
        task_key=body.task_key,
    )
    return {"message_id": message.id}


@router.get("/projects/{project_id}/messages/pending")
async def internal_pending_messages(
    project_id: str, agent: str, session: SessionDep, limit: int = 20
):
    rows = await message_service.pending_for_agent(session, project_id, agent, limit)
    return {
        "messages": [
            {
                "id": m.id,
                "from": m.from_participant,
                "subject": m.subject,
                "body": m.body_md,
                "ack_requested": m.ack_requested,
                "thread_id": m.thread_id,
                "task_key": m.task_key,
                "ts": m.created_at.isoformat(),
            }
            for m in rows
        ]
    }


class NotifiedIn(BaseModel):
    msg_ids: list[str]


@router.post("/projects/{project_id}/messages/notified")
async def internal_mark_notified(
    project_id: str, body: NotifiedIn, session: SessionDep
):
    for msg_id in body.msg_ids:
        await message_service.mark_notified(session, msg_id)
    return {"ok": True}


class AckIn(BaseModel):
    agent: str
    note: str = ""


@router.post("/messages/{msg_id}/ack")
async def internal_ack_message(msg_id: str, body: AckIn, session: SessionDep):
    message = await message_service.ack_message(session, msg_id, body.agent, body.note)
    if not message:
        raise HTTPException(404, "message not found")
    return {"ok": True}


# ── SessionStart context re-injection ────────────────────────────


_WIKI_INDEX_CAP = 4000


def _wiki_context(project: Project) -> list[str]:
    """Inline the wiki index + recent log so onboarding doesn't depend on the
    agent choosing to read it. Falls back to a pointer when unreadable."""
    wiki = Path(project.host_dir or "") / "repo" / ".wiki"
    try:
        index = (wiki / "index.md").read_text().strip()
    except Exception:
        return ["Project memory: read .wiki/index.md before starting work."]
    if len(index) > _WIKI_INDEX_CAP:
        index = (
            index[:_WIKI_INDEX_CAP]
            + "\n… (truncated — read .wiki/index.md for the rest)"
        )
    lines = ["", "## Project memory (wiki)", index]
    try:
        tail = (wiki / "log.md").read_text().strip().splitlines()[-10:]
        lines += ["", "### Recent wiki activity", *tail]
    except Exception:
        pass
    return lines


@router.get("/projects/{project_id}/agents/{agent_name}/context")
async def agent_context(project_id: str, agent_name: str, session: SessionDep):
    """Standing context rebuilt from DB — injected at every session start,
    which makes /clear and compaction safe."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    agent = await _agent_or_404(session, project_id, agent_name)

    team = await session.scalars(
        select(ProjectAgent).where(ProjectAgent.project_id == project_id)
    )
    pending_count = len(
        list(
            await session.scalars(
                select(Message.id).where(
                    Message.project_id == project_id,
                    Message.to_participant.in_([agent_name, "broadcast"]),
                    Message.status.in_(["queued", "notified"]),
                )
            )
        )
    )

    lines = [
        f"# TrembleCode standing context — {agent_name}",
        f"Project: {project.name} (status: {project.status})",
        f"Team: "
        + ", ".join(f"{a.name}[{a.state}]" for a in team),
        f"Pending messages for you: {pending_count}"
        + (" — run check_messages NOW." if pending_count else ""),
        f"Your onboarding page: .wiki/onboarding/{agent.role_key}.md — read it "
        "before your first task.",
        "Team handbook: CLAUDE.md in the repo root.",
    ]

    if agent.current_task_id:
        task = await session.get(Task, agent.current_task_id)
        if task:
            lines += [
                "",
                f"## Your current task: {task.task_key} — {task.title} [{task.status}]",
                f"Branch: {task.branch or '(created on start_task)'}",
                task.description_md,
            ]
    elif agent.kind == "dev":
        lines.append(
            "You have no current task. Check list_tasks(mine=false) for PENDING "
            "tasks matching your role."
        )

    if project.status == "PLANNING" and agent.kind == "lead":
        lines += [
            "",
            "## Planning mode",
            "No approved plan exists yet. Read PRD.md, explore, and produce the "
            "plan via the submit_plan tool (see CLAUDE.md).",
        ]

    lines += _wiki_context(project)

    return {"context": "\n".join(lines)}


# ── Helpers ──────────────────────────────────────────────────────


async def _project_or_404(session, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return project


# ── Tasks (MCP tool backends) ────────────────────────────────────


class TaskActorIn(BaseModel):
    agent: str
    task_id: str


@router.get("/projects/{project_id}/tasks")
async def internal_list_tasks(
    project_id: str, session: SessionDep, status: str = "", agent: str = ""
):
    return {"tasks": await task_service.list_tasks(session, project_id, status, agent)}


@router.post("/projects/{project_id}/tasks/claim")
async def internal_claim_task(project_id: str, body: TaskActorIn, session: SessionDep):
    project = await _project_or_404(session, project_id)
    return await task_service.claim_task(session, project, body.agent, body.task_id)


class AssignIn(TaskActorIn):
    assignee: str


@router.post("/projects/{project_id}/tasks/assign")
async def internal_assign_task(project_id: str, body: AssignIn, session: SessionDep):
    project = await _project_or_404(session, project_id)
    return await task_service.assign_task(
        session, project, body.agent, body.task_id, body.assignee
    )


@router.post("/projects/{project_id}/tasks/start")
async def internal_start_task(project_id: str, body: TaskActorIn, session: SessionDep):
    project = await _project_or_404(session, project_id)
    return await task_service.start_task(session, project, body.agent, body.task_id)


class BlockIn(TaskActorIn):
    reason: str


@router.post("/projects/{project_id}/tasks/block")
async def internal_block_task(project_id: str, body: BlockIn, session: SessionDep):
    project = await _project_or_404(session, project_id)
    return await task_service.block_task(
        session, project, body.agent, body.task_id, body.reason
    )


class ReviewRequestIn(TaskActorIn):
    notes: str = ""


@router.post("/projects/{project_id}/tasks/request-review")
async def internal_request_review(
    project_id: str, body: ReviewRequestIn, session: SessionDep
):
    project = await _project_or_404(session, project_id)
    return await task_service.request_review(
        session, project, body.agent, body.task_id, body.notes
    )


class ReviewIn(TaskActorIn):
    verdict: str
    notes: str = ""


@router.post("/projects/{project_id}/tasks/review")
async def internal_submit_review(project_id: str, body: ReviewIn, session: SessionDep):
    project = await _project_or_404(session, project_id)
    return await task_service.submit_review(
        session, project, body.agent, body.task_id, body.verdict, body.notes
    )


class CompleteIn(TaskActorIn):
    summary: str = ""


@router.post("/projects/{project_id}/tasks/complete")
async def internal_complete_task(
    project_id: str, body: CompleteIn, session: SessionDep
):
    project = await _project_or_404(session, project_id)
    return await task_service.complete_task(
        session, project, body.agent, body.task_id, body.summary
    )


# ── Milestones ───────────────────────────────────────────────────


class MilestoneCompleteIn(BaseModel):
    agent: str
    milestone_id: str
    summary: str = ""


@router.post("/projects/{project_id}/milestones/complete")
async def internal_complete_milestone(
    project_id: str, body: MilestoneCompleteIn, session: SessionDep
):
    project = await _project_or_404(session, project_id)
    lead = await _agent_or_404(session, project_id, body.agent)
    if lead.kind != "lead":
        raise HTTPException(403, "only the lead completes milestones")
    escalation = await escalation_service.open_milestone_gate(
        session, project, body.agent, body.milestone_id, body.summary
    )
    return {
        "escalation_id": escalation.id,
        "note": "Gate opened — wait for the human decision before continuing.",
    }


# ── Escalations ──────────────────────────────────────────────────


class EscalationIn(BaseModel):
    agent: str
    topic: str
    body_md: str = ""
    options: list[str] = []
    blocking: bool = True
    type: str = "question"


@router.post("/projects/{project_id}/escalations")
async def internal_create_escalation(
    project_id: str, body: EscalationIn, session: SessionDep
):
    project = await _project_or_404(session, project_id)
    if body.type not in ("question", "destructive_op"):
        raise HTTPException(422, "type must be question | destructive_op")
    escalation = await escalation_service.create_escalation(
        session,
        project,
        body.agent,
        topic=body.topic,
        body_md=body.body_md,
        options=body.options,
        blocking=body.blocking,
        type=body.type,
    )
    return {
        "escalation_id": escalation.id,
        "note": "Escalation filed. If blocking, end your turn and wait to be notified.",
    }


# ── Plan submission ──────────────────────────────────────────────


class PlanSubmitIn(BaseModel):
    agent: str
    plan: dict


@router.post("/projects/{project_id}/plan/submit")
async def internal_submit_plan(
    project_id: str, body: PlanSubmitIn, session: SessionDep
):
    project = await _project_or_404(session, project_id)
    lead = await _agent_or_404(session, project_id, body.agent)
    if lead.kind != "lead":
        raise HTTPException(403, "only the lead submits plans")
    plan, errors = await plan_service.submit_plan(session, project, body.plan)
    if errors:
        return {"ok": False, "validation_errors": errors}
    return {
        "ok": True,
        "version": plan.version,
        "note": "Plan submitted for human review. Wait for the decision.",
    }


# ── MCP suggestions ──────────────────────────────────────────────


class McpSuggestIn(BaseModel):
    agent: str
    suggestions: list[dict]


@router.post("/projects/{project_id}/mcp-suggestions")
async def internal_suggest_mcp(
    project_id: str, body: McpSuggestIn, session: SessionDep
):
    from ..services.mcp_catalog import catalog_entry

    project = await _project_or_404(session, project_id)
    accepted, unknown = [], []
    for suggestion in body.suggestions:
        name = suggestion.get("name", "")
        entry = catalog_entry(name)
        if entry is None:
            unknown.append(name)
            continue
        existing = await session.scalar(
            select(McpSuggestion).where(
                McpSuggestion.project_id == project_id, McpSuggestion.name == name
            )
        )
        if existing:
            continue
        session.add(
            McpSuggestion(
                project_id=project_id,
                name=name,
                transport=entry.get("transport", "stdio"),
                command=entry.get("command", ""),
                args=entry.get("args", []),
                env_keys=entry.get("env_keys", []),
                reason=suggestion.get("reason", ""),
            )
        )
        accepted.append(name)
    await session.commit()
    if accepted:
        await manager.broadcast("mcp.suggested", project_id, {"names": accepted})
    return {"ok": True, "accepted": accepted, "unknown": unknown}


# ── Dev server registry ──────────────────────────────────────────


class ServiceIn(BaseModel):
    agent: str
    name: str
    container_port: int


@router.post("/projects/{project_id}/services")
async def internal_register_service(
    project_id: str, body: ServiceIn, session: SessionDep
):
    from ..config import get_settings

    project = await _project_or_404(session, project_id)
    settings = get_settings()
    block = range(
        project.port_base, project.port_base + settings.port_block_size
    )

    existing = await session.scalar(
        select(Service).where(
            Service.project_id == project_id, Service.name == body.name
        )
    )
    used = {
        s.host_port
        for s in await session.scalars(
            select(Service).where(Service.project_id == project_id)
        )
        if not existing or s.id != existing.id
    }

    if body.container_port in block and body.container_port not in used:
        port = body.container_port
    else:
        free = [p for p in block if p not in used]
        if not free:
            raise HTTPException(409, "no free ports in this project's block")
        port = free[0]

    if existing:
        existing.container_port = port
        existing.host_port = port
        existing.agent_name = body.agent
        existing.status = "up"
        service = existing
    else:
        service = Service(
            project_id=project_id,
            name=body.name,
            agent_name=body.agent,
            container_port=port,
            host_port=port,
        )
        session.add(service)
    await session.commit()
    await manager.broadcast(
        "service.registered",
        project_id,
        {"name": body.name, "host_port": port},
    )
    note = (
        "" if port == body.container_port
        else f" NOTE: requested port {body.container_port} is outside your block/taken — bind to {port} instead."
    )
    return {
        "host_port": port,
        "container_port": port,
        "url": f"http://localhost:{port}",
        "note": f"Bind your server to 0.0.0.0:{port} (pass --port explicitly).{note}",
    }


# ── Project info (get_project_info tool) ─────────────────────────


@router.get("/projects/{project_id}/info")
async def internal_project_info(project_id: str, session: SessionDep):
    from ..config import get_settings

    project = await _project_or_404(session, project_id)
    services = list(
        await session.scalars(
            select(Service).where(Service.project_id == project_id)
        )
    )
    milestones = list(
        await session.scalars(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.sort)
        )
    )
    active = next((m for m in milestones if m.status == "active"), None)
    block_size = get_settings().port_block_size
    return {
        "name": project.name,
        "status": project.status,
        "active_milestone": (
            {"id": active.id, "key": active.key, "name": active.name} if active else None
        ),
        "milestones": [
            {"id": m.id, "key": m.key, "name": m.name, "status": m.status}
            for m in milestones
        ],
        "port_block": (
            list(range(project.port_base, project.port_base + block_size))
            if project.port_base
            else []
        ),
        "services": [
            {
                "name": s.name,
                "container_port": s.container_port,
                "host_port": s.host_port,
                "url": f"http://localhost:{s.host_port}",
                "registered_by": s.agent_name,
            }
            for s in services
        ],
    }


# ── Costs ────────────────────────────────────────────────────────


class CostsIn(BaseModel):
    agent: str
    events: list[dict]


@router.post("/projects/{project_id}/costs")
async def internal_ingest_costs(project_id: str, body: CostsIn, session: SessionDep):
    from ..services import cost_service

    inserted = await cost_service.ingest_events(
        session, project_id, body.agent, body.events
    )
    if inserted:
        await manager.broadcast("cost.updated", project_id, {"events": inserted})
    return {"ok": True, "inserted": inserted}


# ── Agent requests (lead asks to grow the team; human approves) ──


class AgentRequestIn(BaseModel):
    agent: str
    role_key: str
    count: int = 1
    reason: str = ""


@router.post("/projects/{project_id}/agent-requests")
async def internal_request_agents(
    project_id: str, body: AgentRequestIn, session: SessionDep
):
    from ..models import AgentRequest, AgentTemplate

    project = await _project_or_404(session, project_id)
    requester = await _agent_or_404(session, project_id, body.agent)
    if requester.kind != "lead":
        raise HTTPException(403, "only the lead can request new agents")
    template = await session.scalar(
        select(AgentTemplate).where(AgentTemplate.role_key == body.role_key)
    )
    if not template:
        raise HTTPException(404, f"no agent template for role '{body.role_key}'")
    if template.kind == "lead":
        raise HTTPException(409, "cannot request another lead")
    count = max(1, min(body.count, 4))

    request = AgentRequest(
        project_id=project_id,
        requested_by=body.agent,
        role_key=body.role_key,
        count=count,
        reason=body.reason,
    )
    session.add(request)
    await session.flush()
    escalation = await escalation_service.create_escalation(
        session,
        project,
        body.agent,
        topic=f"Team growth: +{count} {template.display_name}",
        body_md=(
            f"The lead requests **{count} additional {template.display_name}"
            f"{'s' if count > 1 else ''}** (`{body.role_key}`).\n\n"
            f"Reason:\n{body.reason or '(none given)'}"
        ),
        options=["approve", "reject"],
        blocking=False,
        type="agent_request",
        ref_id=request.id,
    )
    return {
        "escalation_id": escalation.id,
        "note": (
            "Request filed in the human inbox. You'll be messaged with the "
            "decision; continue other work meanwhile."
        ),
    }
