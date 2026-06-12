"""Task lifecycle. State machine:

PENDING → ASSIGNED → IN_PROGRESS → IN_REVIEW → APPROVED → MERGING → DONE
                ↘ BLOCKED ↙          ↓ CHANGES_REQUESTED → IN_PROGRESS

Invariants enforced here:
- claims/assignments are CAS (no double-assignment);
- a task is only assignable/claimable when all dependencies are DONE;
- at most ONE task per project is MERGING (the lead is the only merger and
  the server serializes the merge queue);
- QA routing picks the least-loaded qa agent.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from slugify import slugify
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Milestone,
    MilestoneStatus,
    Project,
    ProjectAgent,
    Task,
    TaskEvent,
    TaskStatus,
)
from ..ws.manager import manager
from . import bus, git_service, message_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _record(
    session: AsyncSession,
    task: Task,
    actor: str,
    from_status: str | None,
    to_status: str,
    note: str = "",
) -> None:
    session.add(
        TaskEvent(
            task_id=task.id,
            actor=actor,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )
    await manager.broadcast(
        "task.updated",
        task.project_id,
        {"task_key": task.task_key, "status": to_status, "actor": actor},
    )


async def _task_or_404(session: AsyncSession, project_id: str, task_id: str) -> Task:
    task = await session.get(Task, task_id)
    if not task or task.project_id != project_id:
        # allow lookup by task_key as a convenience for agents
        task = await session.scalar(
            select(Task).where(
                Task.project_id == project_id, Task.task_key == task_id
            )
        )
    if not task:
        raise HTTPException(404, f"task '{task_id}' not found")
    return task


async def _deps_done(session: AsyncSession, task: Task) -> list[str]:
    """Returns the list of unfinished dependency keys."""
    if not task.dependencies:
        return []
    rows = await session.scalars(
        select(Task).where(
            Task.project_id == task.project_id,
            Task.task_key.in_(task.dependencies),
        )
    )
    return [t.task_key for t in rows if t.status != TaskStatus.DONE]


async def list_tasks(
    session: AsyncSession, project_id: str, status: str = "", agent: str = ""
) -> list[dict]:
    query = select(Task).where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    agents = {
        a.id: a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project_id)
        )
    }
    rows = list(await session.scalars(query.order_by(Task.task_key)))
    if agent:
        rows = [t for t in rows if agents.get(t.assignee_agent_id) == agent]
    out = []
    for t in rows:
        unmet = await _deps_done(session, t)
        out.append(
            {
                "task_id": t.id,
                "task_key": t.task_key,
                "title": t.title,
                "status": t.status,
                "role_key": t.role_key,
                "assignee": agents.get(t.assignee_agent_id),
                "branch": t.branch,
                "dependencies": t.dependencies,
                "unmet_dependencies": unmet,
                "description_md": t.description_md,
            }
        )
    return out


async def _agent_by_name(
    session: AsyncSession, project_id: str, name: str
) -> ProjectAgent:
    agent = await session.scalar(
        select(ProjectAgent).where(
            ProjectAgent.project_id == project_id, ProjectAgent.name == name
        )
    )
    if not agent:
        raise HTTPException(404, f"agent '{name}' not found")
    return agent


async def _assign(
    session: AsyncSession, project: Project, task: Task, assignee: ProjectAgent, actor: str
) -> dict:
    unmet = await _deps_done(session, task)
    if unmet:
        raise HTTPException(409, f"dependencies not done: {', '.join(unmet)}")
    if assignee.role_key != task.role_key:
        raise HTTPException(
            409, f"task requires role '{task.role_key}', {assignee.name} is '{assignee.role_key}'"
        )
    # CAS: only grab if still unassigned & pending
    result = await session.execute(
        update(Task)
        .where(
            Task.id == task.id,
            Task.status == TaskStatus.PENDING,
            Task.assignee_agent_id.is_(None),
        )
        .values(assignee_agent_id=assignee.id, status=TaskStatus.ASSIGNED)
    )
    if result.rowcount == 0:
        raise HTTPException(409, "already_assigned")
    await _record(session, task, actor, TaskStatus.PENDING, TaskStatus.ASSIGNED)
    assignee.current_task_id = task.id
    await session.commit()

    # context policy: fresh context per task. Publish the clear BEFORE the
    # assignment message so the relay (which delivers in stream order, at
    # idle) wipes context first and the doorbell lands on the fresh session —
    # whose standing context already carries the full task brief.
    # No clear on self-claim: the claimer is mid-turn by definition and the
    # post-complete clear already covered it.
    if actor != assignee.name:
        try:
            await bus.publish(
                project.id,
                {
                    "type": "clear",
                    "to": assignee.name,
                    "reason": f"new task {task.task_key}",
                },
            )
        except Exception:
            logger.exception("clear publish failed")
        # short pointer only — the full brief is in the assignee's standing
        # context and via list_tasks; duplicating it here burns tokens twice
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant=actor,
            to_participant=assignee.name,
            subject=f"Task assigned: {task.task_key} — {task.title}",
            body_md=(
                f"You are assigned **{task.task_key} — {task.title}**. The full "
                "brief is in your standing context (or list_tasks). Run "
                f"start_task(\"{task.id}\") to begin (the server creates the "
                "branch), work in YOUR worktree, then request_review."
            ),
            ack_requested=True,
            task_key=task.task_key,
        )
    return {"ok": True, "task_key": task.task_key}


async def claim_task(
    session: AsyncSession, project: Project, agent_name: str, task_id: str
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    task = await _task_or_404(session, project.id, task_id)
    return await _assign(session, project, task, agent, actor=agent_name)


async def assign_task(
    session: AsyncSession, project: Project, lead_name: str, task_id: str, assignee_name: str
) -> dict:
    lead = await _agent_by_name(session, project.id, lead_name)
    if lead.kind != "lead":
        raise HTTPException(403, "only the lead can assign tasks")
    assignee = await _agent_by_name(session, project.id, assignee_name)
    task = await _task_or_404(session, project.id, task_id)
    return await _assign(session, project, task, assignee, actor=lead_name)


async def start_task(
    session: AsyncSession, project: Project, agent_name: str, task_id: str
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    task = await _task_or_404(session, project.id, task_id)
    if task.assignee_agent_id != agent.id:
        raise HTTPException(403, "task is not assigned to you")
    if task.status not in (TaskStatus.ASSIGNED, TaskStatus.BLOCKED):
        raise HTTPException(409, f"task is {task.status}")
    if not task.branch:
        task.branch = f"task/{task.task_key.lower()}-{slugify(task.title)[:30]}"
        repo = Path(project.host_dir) / "repo"
        try:
            await git_service.run_git(["branch", task.branch, "main"], repo)
        except git_service.GitError as exc:
            if "already exists" not in str(exc):
                raise HTTPException(500, str(exc))
    prev = task.status
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = task.started_at or _now()
    task.blocked_reason = None
    agent.current_task_id = task.id
    await _record(session, task, agent_name, prev, TaskStatus.IN_PROGRESS)
    await session.commit()
    return {
        "ok": True,
        "branch": task.branch,
        "hint": f"git checkout {task.branch} (in your worktree)",
    }


async def block_task(
    session: AsyncSession, project: Project, agent_name: str, task_id: str, reason: str
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    task = await _task_or_404(session, project.id, task_id)
    if task.assignee_agent_id != agent.id:
        raise HTTPException(403, "task is not assigned to you")
    prev = task.status
    task.status = TaskStatus.BLOCKED
    task.blocked_reason = reason
    await _record(session, task, agent_name, prev, TaskStatus.BLOCKED, reason)
    await session.commit()
    return {"ok": True}


async def _pick_reviewer(session: AsyncSession, project_id: str) -> ProjectAgent:
    qa_agents = list(
        await session.scalars(
            select(ProjectAgent).where(
                ProjectAgent.project_id == project_id, ProjectAgent.kind == "qa"
            )
        )
    )
    if not qa_agents:
        raise HTTPException(409, "no QA agent on this team")
    loads: list[tuple[int, ProjectAgent]] = []
    for qa in qa_agents:
        load = await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.review_agent_id == qa.id, Task.status == TaskStatus.IN_REVIEW
            )
        )
        loads.append((load or 0, qa))
    loads.sort(key=lambda pair: pair[0])
    return loads[0][1]


async def request_review(
    session: AsyncSession, project: Project, agent_name: str, task_id: str, notes: str
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    task = await _task_or_404(session, project.id, task_id)
    if task.assignee_agent_id != agent.id:
        raise HTTPException(403, "task is not assigned to you")
    if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.CHANGES_REQUESTED):
        raise HTTPException(409, f"task is {task.status}")
    reviewer = await _pick_reviewer(session, project.id)
    prev = task.status
    task.status = TaskStatus.IN_REVIEW
    task.review_agent_id = reviewer.id
    await _record(session, task, agent_name, prev, TaskStatus.IN_REVIEW)
    await session.commit()
    await message_service.create_message(
        session,
        project_id=project.id,
        from_participant=agent_name,
        to_participant=reviewer.name,
        subject=f"Review requested: {task.task_key} — {task.title}",
        body_md=(
            f"Please review **{task.task_key} — {task.title}** on branch "
            f"`{task.branch}`. Fetch the brief with list_tasks.\n\n"
            f"Developer notes:\n{notes}\n\n"
            f"Check out the branch DETACHED in your worktree "
            f"(`git checkout --detach {task.branch}`), run the full suite, "
            f"verify the acceptance criteria for real, then submit_review."
        ),
        ack_requested=True,
        task_key=task.task_key,
    )
    out: dict = {"ok": True, "reviewer": reviewer.name}
    # soft ingest check: warn (don't reject) when the branch carries no wiki
    # changes — some tasks genuinely have nothing to record
    try:
        diff = await git_service.run_git(
            ["diff", "--name-only", f"main...{task.branch}"],
            Path(project.host_dir) / "repo",
        )
        if not any(p.startswith(".wiki/") for p in diff.splitlines()):
            out["warning"] = (
                "No .wiki/ changes on this branch — do the wiki ingest "
                "(pages, index.md, log.md entry) before QA picks this up."
            )
    except Exception:
        logger.exception("wiki ingest check failed for %s", task.task_key)
    return out


async def _promote_next_merge(session: AsyncSession, project: Project) -> None:
    """If nothing is merging, promote the oldest APPROVED task and brief the
    lead. Keeps merges strictly serial."""
    merging = await session.scalar(
        select(Task).where(
            Task.project_id == project.id, Task.status == TaskStatus.MERGING
        )
    )
    if merging:
        return
    next_task = await session.scalar(
        select(Task)
        .where(Task.project_id == project.id, Task.status == TaskStatus.APPROVED)
        .order_by(Task.updated_at)
        .limit(1)
    )
    if not next_task:
        return
    prev = next_task.status
    next_task.status = TaskStatus.MERGING
    await _record(session, next_task, "system", prev, TaskStatus.MERGING)
    await session.commit()

    agents = {
        a.id: a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project.id)
        )
    }
    dev = agents.get(next_task.assignee_agent_id, "?")
    await message_service.create_message(
        session,
        project_id=project.id,
        from_participant="system",
        to_participant="lead",
        subject=f"Merge now: {next_task.task_key} ({next_task.branch})",
        body_md=(
            f"QA approved **{next_task.task_key} — {next_task.title}** "
            f"(branch `{next_task.branch}`, developer {dev}). Merge per the "
            f"handbook merge procedure (CLAUDE.md), then "
            f"complete_task(\"{next_task.id}\")."
        ),
        ack_requested=True,
        task_key=next_task.task_key,
    )


async def submit_review(
    session: AsyncSession,
    project: Project,
    agent_name: str,
    task_id: str,
    verdict: str,
    notes: str,
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    if agent.kind != "qa":
        raise HTTPException(403, "only QA agents submit reviews")
    task = await _task_or_404(session, project.id, task_id)
    if task.status != TaskStatus.IN_REVIEW:
        raise HTTPException(409, f"task is {task.status}")
    if task.review_agent_id != agent.id:
        raise HTTPException(403, "this review is routed to another QA agent")
    if verdict not in ("approve", "request_changes"):
        raise HTTPException(422, "verdict must be approve | request_changes")

    agents = {
        a.id: a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project.id)
        )
    }
    dev = agents.get(task.assignee_agent_id, "lead")

    if verdict == "approve":
        task.status = TaskStatus.APPROVED
        await _record(session, task, agent_name, TaskStatus.IN_REVIEW, TaskStatus.APPROVED, notes)
        await session.commit()
        await _promote_next_merge(session, project)
    else:
        task.status = TaskStatus.CHANGES_REQUESTED
        await _record(
            session, task, agent_name, TaskStatus.IN_REVIEW, TaskStatus.CHANGES_REQUESTED, notes
        )
        await session.commit()
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant=agent_name,
            to_participant=dev,
            subject=f"Changes requested: {task.task_key}",
            body_md=f"Review of **{task.task_key}** found issues:\n\n{notes}\n\n"
            "Fix on the same branch, then request_review again.",
            ack_requested=True,
            task_key=task.task_key,
        )
    # QA gets a fresh context after each delivered review
    try:
        await bus.publish(
            project.id,
            {"type": "clear", "to": agent_name, "reason": f"review of {task.task_key} done"},
        )
    except Exception:
        logger.exception("clear publish failed")
    return {"ok": True, "verdict": verdict}


async def complete_task(
    session: AsyncSession, project: Project, agent_name: str, task_id: str, summary: str
) -> dict:
    agent = await _agent_by_name(session, project.id, agent_name)
    if agent.kind != "lead":
        raise HTTPException(403, "only the lead completes tasks")
    task = await _task_or_404(session, project.id, task_id)
    if task.status != TaskStatus.MERGING:
        raise HTTPException(409, f"task is {task.status} (complete only MERGING tasks)")

    task.status = TaskStatus.DONE
    task.completed_at = _now()
    await _record(session, task, agent_name, TaskStatus.MERGING, TaskStatus.DONE, summary)

    assignee = await session.get(ProjectAgent, task.assignee_agent_id)
    if assignee and assignee.current_task_id == task.id:
        assignee.current_task_id = None
    await session.commit()

    if assignee:
        await message_service.create_message(
            session,
            project_id=project.id,
            from_participant=agent_name,
            to_participant=assignee.name,
            subject=f"{task.task_key} merged — task DONE",
            body_md=(
                f"**{task.task_key}** is merged into main. Your context will be "
                "cleared next; afterwards check list_tasks for your next "
                "PENDING task."
            ),
            task_key=task.task_key,
        )
        # context policy: fresh context per task (relay injects /clear at idle,
        # AFTER the message above has been read)
        try:
            await bus.publish(
                project.id,
                {"type": "clear", "to": assignee.name, "reason": f"{task.task_key} done"},
            )
        except Exception:
            logger.exception("clear publish failed")

    await _promote_next_merge(session, project)

    # surface newly unblocked tasks + milestone completion to the lead
    pending = await session.scalars(
        select(Task).where(
            Task.project_id == project.id, Task.status == TaskStatus.PENDING
        )
    )
    ready = [
        t.task_key for t in pending if not await _deps_done(session, t)
    ]
    milestone_note = ""
    if task.milestone_id:
        remaining = await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.milestone_id == task.milestone_id,
                Task.status != TaskStatus.DONE,
            )
        )
        if remaining == 0:
            milestone = await session.get(Milestone, task.milestone_id)
            milestone_note = (
                f" All tasks of milestone {milestone.key} are DONE — write the "
                f"demo summary and call complete_milestone(\"{milestone.id}\")."
            )
    return {
        "ok": True,
        "ready_tasks": ready,
        "note": (f"Assignable now: {', '.join(ready)}." if ready else "")
        + milestone_note,
    }
