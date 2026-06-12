"""Pre-PRD discussion: a host-side headless Claude chat that interviews the
user about their idea and finally produces the PRD markdown.

Runs the host's `claude` CLI in -p mode with --resume for continuity. No
tools are needed; it's a pure conversation."""

import asyncio
import json
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Discussion, DiscussionMessage, Project, ProjectStatus
from ..ws.manager import manager

logger = logging.getLogger(__name__)

INTERVIEWER_PROMPT = """You are a senior product manager interviewing a client
about a software project they want an autonomous agent team to build.

Rules:
- Ask focused questions (2-4 at a time, max) to uncover: the problem, target
  users, core features, target platform (web app / API / mobile / Flutter /
  CLI), tech preferences/constraints, what's explicitly OUT of scope, and what
  a successful first milestone looks like.
- Be concrete and concise; propose sensible defaults the client can accept.
- When you believe you have enough (or the client says to wrap up), say you're
  ready to write the PRD and summarize the key decisions.
- When the client asks for the final PRD, respond with ONLY the PRD as clean
  markdown: # title, ## Overview, ## Goals, ## Non-goals, ## Target users,
  ## Features (per milestone), ## Technical notes, ## Acceptance criteria.
"""

FINALIZE_PROMPT = (
    "Produce the final PRD now, as pure markdown only — no preamble, no "
    "questions, no commentary."
)


async def _run_claude(prompt: str, session_id: str | None) -> tuple[str, str]:
    """Returns (reply_text, session_id)."""
    args = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--append-system-prompt",
        INTERVIEWER_PROMPT,
        "--disallowed-tools",
        "*",
    ]
    if session_id:
        args += ["--resume", session_id]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "discussion model timed out")
    if proc.returncode != 0:
        raise HTTPException(
            502, f"claude CLI failed: {err.decode(errors='replace')[:500]}"
        )
    try:
        data = json.loads(out.decode())
    except json.JSONDecodeError:
        raise HTTPException(502, "claude CLI returned non-JSON output")
    return data.get("result", ""), data.get("session_id", session_id or "")


async def _get_or_create(session: AsyncSession, project: Project) -> Discussion:
    discussion = await session.scalar(
        select(Discussion).where(Discussion.project_id == project.id)
    )
    if discussion is None:
        discussion = Discussion(project_id=project.id)
        session.add(discussion)
        await session.commit()
    return discussion


async def post_message(
    session: AsyncSession, project: Project, content: str
) -> DiscussionMessage:
    discussion = await _get_or_create(session, project)
    session.add(
        DiscussionMessage(discussion_id=discussion.id, role="user", content=content)
    )
    await session.commit()

    reply, session_id = await _run_claude(content, discussion.claude_session_id)
    discussion.claude_session_id = session_id
    message = DiscussionMessage(
        discussion_id=discussion.id, role="assistant", content=reply
    )
    session.add(message)
    await session.commit()
    await manager.broadcast("project.discussion", project.id, {})
    return message


async def finalize(session: AsyncSession, project: Project) -> str:
    discussion = await _get_or_create(session, project)
    if not discussion.claude_session_id:
        raise HTTPException(409, "no discussion to finalize — chat first")
    prd, session_id = await _run_claude(FINALIZE_PROMPT, discussion.claude_session_id)
    discussion.claude_session_id = session_id
    discussion.status = "finalized"
    project.prd_md = prd
    if project.status == ProjectStatus.DISCUSSION:
        project.status = ProjectStatus.DRAFT
    session.add(
        DiscussionMessage(discussion_id=discussion.id, role="assistant", content=prd)
    )
    await session.commit()
    await manager.broadcast("project.updated", project.id, {"prd": True})
    return prd
