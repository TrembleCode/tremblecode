"""The `tremblecode` MCP server — one stdio instance per agent session.

Identifies its agent via TC_AGENT (set on the tmux session, inherited by
Claude Code, inherited by this process). All tools are thin HTTP calls to the
local relay; the relay/server enforce role gating and persistence.
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

AGENT = os.environ.get("TC_AGENT", "unknown")
RELAY = os.environ.get("TC_RELAY", "http://127.0.0.1:8765")

mcp = FastMCP("tremblecode")
_client = httpx.Client(base_url=RELAY, timeout=30)


def _post(path: str, body: dict) -> dict:
    res = _client.post(path, json=body)
    if res.status_code >= 400:
        return {"error": f"{res.status_code}: {res.text[:500]}"}
    return res.json()


def _get(path: str, params: dict | None = None) -> dict:
    res = _client.get(path, params=params or {})
    if res.status_code >= 400:
        return {"error": f"{res.status_code}: {res.text[:500]}"}
    return res.json()


# ── Communication ────────────────────────────────────────────────


@mcp.tool()
def send_message(
    to: str,
    body: str,
    subject: str = "",
    ack_requested: bool = False,
    thread_id: str = "",
    priority: str = "normal",
    task_key: str = "",
) -> dict:
    """Send a message to a teammate ('lead', 'be-1', ...), 'human' (the
    Product Owner) or 'broadcast' (everyone). Set ack_requested=true when you
    need delivery certainty — the recipient must ack_message it. Use
    thread_id to keep a conversation grouped."""
    return _post(
        "/messages/send",
        {
            "from_agent": AGENT,
            "to": to,
            "body_md": body,
            "subject": subject,
            "ack_requested": ack_requested,
            "thread_id": thread_id or None,
            "priority": priority,
            "task_key": task_key or None,
        },
    )


@mcp.tool()
def check_messages(max_messages: int = 20) -> dict:
    """Fetch your pending messages (full bodies). Call this immediately
    whenever you see an [TREMBLECODE] notification line. Ack anything with
    ack_requested=true via ack_message BEFORE acting on it."""
    return _get("/messages/pending", {"agent": AGENT, "limit": max_messages})


@mcp.tool()
def ack_message(message_id: str, note: str = "") -> dict:
    """Acknowledge a message you received. The sender gets a receipt."""
    return _post(f"/messages/{message_id}/ack", {"agent": AGENT, "note": note})


@mcp.tool()
def report_status(state: str, detail: str = "") -> dict:
    """Report your activity to the team dashboard.
    state: working | idle | blocked | waiting"""
    return _post("/status", {"agent": AGENT, "state": state, "detail": detail})


@mcp.tool()
def get_team() -> dict:
    """Live team roster: every agent's name, role, model and current state."""
    return _get("/team")


@mcp.tool()
def get_project_info() -> dict:
    """Project status, milestone, registered dev servers and the port table."""
    return _get("/project-info")


# ── Escalation (hot topics only) ─────────────────────────────────


@mcp.tool()
def escalate_to_human(
    topic: str,
    body: str,
    options: list[str] | None = None,
    blocking: bool = True,
    type: str = "question",
) -> dict:
    """Open a hot topic in the Product Owner's inbox. Use ONLY for: ambiguous
    requirements the lead can't resolve, destructive/irreversible operations,
    external paid services, or being hard-blocked. type: question |
    destructive_op. If blocking=true, end your turn after calling this and
    wait to be notified of the answer."""
    return _post(
        "/server/projects/{project_id}/escalations",
        {
            "agent": AGENT,
            "topic": topic,
            "body_md": body,
            "options": options or [],
            "blocking": blocking,
            "type": type,
        },
    )


# ── Tasks ────────────────────────────────────────────────────────


@mcp.tool()
def list_tasks(status: str = "", mine: bool = False) -> dict:
    """List project tasks. Filter by status (PENDING, IN_PROGRESS, ...) or
    mine=true for tasks assigned to you."""
    return _get(
        "/server/projects/{project_id}/tasks",
        {"status": status, "agent": AGENT if mine else ""},
    )


@mcp.tool()
def claim_task(task_id: str) -> dict:
    """Claim an unassigned PENDING task matching your role (atomic — fails if
    someone claimed it first)."""
    return _post(
        "/server/projects/{project_id}/tasks/claim",
        {"agent": AGENT, "task_id": task_id},
    )


@mcp.tool()
def assign_task(task_id: str, agent: str) -> dict:
    """[lead only] Assign a task to a team member. The server notifies the
    assignee and refreshes their context with the brief automatically — do
    NOT send a separate brief message."""
    return _post(
        "/server/projects/{project_id}/tasks/assign",
        {"agent": AGENT, "task_id": task_id, "assignee": agent},
    )


@mcp.tool()
def start_task(task_id: str) -> dict:
    """Start your assigned task. The server creates the task branch; check it
    out in YOUR worktree and work there."""
    return _post(
        "/server/projects/{project_id}/tasks/start",
        {"agent": AGENT, "task_id": task_id},
    )


@mcp.tool()
def block_task(task_id: str, reason: str) -> dict:
    """Mark your task BLOCKED with a concrete reason. Message whoever can
    unblock you."""
    return _post(
        "/server/projects/{project_id}/tasks/block",
        {"agent": AGENT, "task_id": task_id, "reason": reason},
    )


@mcp.tool()
def request_review(task_id: str, notes: str) -> dict:
    """Submit your finished task for QA review. Include concrete verification
    notes: what to run, what to check, acceptance criteria covered. Commit and
    push your branch first; do your wiki ingest first."""
    return _post(
        "/server/projects/{project_id}/tasks/request-review",
        {"agent": AGENT, "task_id": task_id, "notes": notes},
    )


@mcp.tool()
def submit_review(task_id: str, verdict: str, notes: str) -> dict:
    """[qa only] Deliver your review verdict: 'approve' or 'request_changes'.
    For request_changes, notes must be a concrete numbered checklist."""
    return _post(
        "/server/projects/{project_id}/tasks/review",
        {"agent": AGENT, "task_id": task_id, "verdict": verdict, "notes": notes},
    )


@mcp.tool()
def complete_task(task_id: str, summary: str) -> dict:
    """[lead only] Mark a task DONE after you merged its branch and the smoke
    check passed."""
    return _post(
        "/server/projects/{project_id}/tasks/complete",
        {"agent": AGENT, "task_id": task_id, "summary": summary},
    )


@mcp.tool()
def complete_milestone(milestone_id: str, summary: str) -> dict:
    """[lead only] Declare a milestone finished. Opens a human gate in the
    inbox; wait for the decision before starting the next milestone. Include
    a demo summary: what works, how to see it, preview URLs."""
    return _post(
        "/server/projects/{project_id}/milestones/complete",
        {"agent": AGENT, "milestone_id": milestone_id, "summary": summary},
    )


# ── Planning (lead) ──────────────────────────────────────────────


@mcp.tool()
def submit_plan(plan_package: dict) -> dict:
    """[lead only] Submit the project plan for human review. Schema:
    {specs_md, risks_md, user_stories: [{story_key, role, action, benefit,
    acceptance_md}], milestones: [{key, name, description}], tasks:
    [{task_key, title, description_md, role_key, milestone_key,
    dependencies: [task_key], estimate_h}], mcp_suggestions: [{name, reason}]}.
    Validation errors come back — fix and resubmit."""
    return _post(
        "/server/projects/{project_id}/plan/submit",
        {"agent": AGENT, "plan": plan_package},
    )


@mcp.tool()
def request_agents(role_key: str, count: int = 1, reason: str = "") -> dict:
    """[lead only] Ask the human to approve adding teammates of an existing
    figure (role_key from get_team / the roster, e.g. 'qa', 'backend_dev').
    Use when the team is a bottleneck: reviews queueing up, parallelizable
    work idle. Give a concrete reason. Non-blocking — continue working; you'll
    be messaged with the decision and the new agents' names."""
    return _post(
        "/server/projects/{project_id}/agent-requests",
        {"agent": AGENT, "role_key": role_key, "count": count, "reason": reason},
    )


@mcp.tool()
def suggest_mcp_servers(suggestions: list[dict]) -> dict:
    """[lead only] Suggest MCP servers to attach to the team, from the
    catalog shown in your planning instructions. Each: {name, reason}.
    The human approves them in the dashboard."""
    return _post(
        "/server/projects/{project_id}/mcp-suggestions",
        {"agent": AGENT, "suggestions": suggestions},
    )


# ── Dev servers ──────────────────────────────────────────────────


@mcp.tool()
def register_service(name: str, container_port: int) -> dict:
    """Register a dev server BEFORE starting it. Returns the port you must
    bind to (always pass --port explicitly and listen on 0.0.0.0) and the
    host URL where humans can see it."""
    return _post(
        "/server/projects/{project_id}/services",
        {"agent": AGENT, "name": name, "container_port": container_port},
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
