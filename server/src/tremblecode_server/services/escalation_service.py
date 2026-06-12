import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Escalation,
    EscalationStatus,
    Milestone,
    MilestoneStatus,
    Project,
    ProjectAgent,
    ProjectStatus,
    Task,
    TaskStatus,
)
from ..ws.manager import manager
from . import message_service

logger = logging.getLogger(__name__)


async def create_escalation(
    session: AsyncSession,
    project: Project,
    agent_name: str,
    *,
    topic: str,
    body_md: str,
    options: list[str],
    blocking: bool,
    type: str,
    ref_id: str | None = None,
) -> Escalation:
    agent = await session.scalar(
        select(ProjectAgent).where(
            ProjectAgent.project_id == project.id, ProjectAgent.name == agent_name
        )
    )
    escalation = Escalation(
        project_id=project.id,
        agent_id=agent.id if agent else None,
        agent_name=agent_name,
        type=type,
        topic=topic,
        body_md=body_md,
        options=options,
        blocking=blocking,
        ref_id=ref_id,
    )
    session.add(escalation)
    if agent and blocking:
        agent.state = "waiting_human"
    await session.commit()
    await manager.broadcast(
        "escalation.new",
        project.id,
        {"id": escalation.id, "type": type, "topic": topic, "agent": agent_name},
    )
    return escalation


async def respond(
    session: AsyncSession, escalation: Escalation, response_md: str, option: str | None
) -> None:
    if escalation.status != EscalationStatus.OPEN:
        raise HTTPException(409, "escalation already handled")
    escalation.status = EscalationStatus.ANSWERED
    escalation.response_md = response_md if not option else f"{option}\n\n{response_md}".strip()
    escalation.responded_at = datetime.now(timezone.utc)
    await session.commit()

    project = await session.get(Project, escalation.project_id)

    if escalation.type == "milestone_gate" and escalation.ref_id:
        await _handle_milestone_gate(session, project, escalation, option or response_md)
        return

    if escalation.type == "agent_request" and escalation.ref_id:
        await _handle_agent_request(session, project, escalation, option or response_md)
        return

    # route the answer back to the asking agent
    if escalation.agent_name not in ("system", "human"):
        await message_service.create_message(
            session,
            project_id=escalation.project_id,
            from_participant="human",
            to_participant=escalation.agent_name,
            subject=f"Answer: {escalation.topic}",
            body_md=escalation.response_md or "(no comment)",
            ack_requested=True,
        )
    await manager.broadcast(
        "escalation.answered", escalation.project_id, {"id": escalation.id}
    )


async def _handle_agent_request(
    session: AsyncSession, project: Project, escalation: Escalation, decision: str
) -> None:
    from ..models import AgentRequest
    from . import agent_service

    request = await session.get(AgentRequest, escalation.ref_id)
    approved = decision.strip().lower().startswith("approve")
    if not request:
        return
    if approved:
        names = []
        for _ in range(request.count):
            agent = await agent_service.add_agent(
                session, project, request.role_key, request.model
            )
            names.append(agent.name)
        request.status = "approved"
        await session.commit()
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant="human",
            to_participant=request.requested_by,
            subject="Team growth approved",
            body_md=(
                f"Approved: {', '.join(f'`{n}`' for n in names)} "
                f"({request.role_key}) joining the team — online within a few "
                "seconds. Brief them by message and assign work as needed. "
                f"{escalation.response_md or ''}"
            ),
            ack_requested=True,
        )
    else:
        request.status = "rejected"
        await session.commit()
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant="human",
            to_participant=request.requested_by,
            subject="Team growth rejected",
            body_md=(
                "Your request for additional agents was rejected. "
                f"Feedback: {escalation.response_md or '(none)'}"
            ),
            ack_requested=True,
        )
    await manager.broadcast(
        "escalation.answered", project.id, {"id": escalation.id}
    )


async def _handle_milestone_gate(
    session: AsyncSession, project: Project, escalation: Escalation, decision: str
) -> None:
    milestone = await session.get(Milestone, escalation.ref_id)
    approved = decision.strip().lower().startswith("approve")
    if approved and milestone:
        milestone.status = MilestoneStatus.APPROVED
        next_milestone = await session.scalar(
            select(Milestone)
            .where(
                Milestone.plan_id == milestone.plan_id,
                Milestone.sort > milestone.sort,
            )
            .order_by(Milestone.sort)
            .limit(1)
        )
        body: str
        if next_milestone:
            next_milestone.status = MilestoneStatus.ACTIVE
            body = (
                f"Milestone {milestone.key} APPROVED. Before starting milestone "
                f"{next_milestone.key} ({next_milestone.name}): run the wiki "
                "LINT pass per .wiki/conventions.md (orphan pages, broken "
                "links, contradictions, stale index entries), commit the "
                "fixes, log the pass in log.md. Then assign the new "
                "milestone's dependency-free tasks."
            )
        else:
            remaining = await session.scalar(
                select(Task).where(
                    Task.project_id == project.id, Task.status != TaskStatus.DONE
                )
            )
            if remaining is None:
                project.status = ProjectStatus.COMPLETED
                body = (
                    f"Milestone {milestone.key} APPROVED — that was the last "
                    "one. Run the final wiki lint, write a closing report to "
                    "the human, the project is COMPLETE. Congratulations."
                )
            else:
                body = (
                    f"Milestone {milestone.key} APPROVED — but some tasks are "
                    "still open. Finish them."
                )
        await session.commit()
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant="human",
            to_participant="lead",
            subject=f"Milestone {milestone.key}: APPROVED",
            body_md=body,
            ack_requested=True,
        )
    else:
        if milestone:
            milestone.status = MilestoneStatus.ACTIVE
        await session.commit()
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant="human",
            to_participant="lead",
            subject=f"Milestone {milestone.key if milestone else ''}: changes requested",
            body_md=(
                "The milestone gate was NOT approved. Feedback:\n\n"
                f"{escalation.response_md or '(none)'}\n\n"
                "Create/adjust tasks to address it, then complete the "
                "milestone again."
            ),
            ack_requested=True,
        )
    await manager.broadcast(
        "escalation.answered", project.id, {"id": escalation.id}
    )


async def open_milestone_gate(
    session: AsyncSession, project: Project, lead_name: str, milestone_id: str, summary: str
) -> Escalation:
    milestone = await session.get(Milestone, milestone_id)
    if not milestone or milestone.project_id != project.id:
        raise HTTPException(404, "milestone not found")
    open_tasks = await session.scalar(
        select(Task).where(
            Task.milestone_id == milestone.id, Task.status != TaskStatus.DONE
        )
    )
    if open_tasks is not None:
        raise HTTPException(409, "milestone still has unfinished tasks")
    milestone.status = MilestoneStatus.GATE_OPEN
    await session.commit()
    return await create_escalation(
        session,
        project,
        lead_name,
        topic=f"Milestone gate: {milestone.key} — {milestone.name}",
        body_md=summary,
        options=["approve", "request changes"],
        blocking=True,
        type="milestone_gate",
        ref_id=milestone.id,
    )
