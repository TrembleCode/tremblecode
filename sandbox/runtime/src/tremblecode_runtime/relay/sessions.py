"""tmux session reconciler: keeps one Claude Code session per desired agent.

Desired state comes from the server (/internal/projects/{id}/agents); the
loop creates missing tmux sessions, relaunches crashed ones (claude
--continue) and tears down sessions for removed agents.
"""

import asyncio
import json
import logging
import os
import shlex
from pathlib import Path

import httpx

from ..config import get_config
from . import tmux
from .state import state

logger = logging.getLogger(__name__)


def seed_claude_config(workspace: str) -> None:
    """Pre-seed ~/.claude.json so fresh sessions skip onboarding and the
    workspace-trust dialog (concurrent last-writer-wins is acceptable here)."""
    path = Path.home() / ".claude.json"
    try:
        config = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        config = {}
    config.setdefault("theme", "dark")
    config["hasCompletedOnboarding"] = True
    projects = config.setdefault("projects", {})
    entry = projects.setdefault(workspace, {})
    entry["hasTrustDialogAccepted"] = True
    entry.setdefault("hasCompletedProjectOnboarding", True)
    entry["enableAllProjectMcpServers"] = True
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key and len(api_key) > 20:
        approved = config.setdefault("customApiKeyResponses", {}).setdefault(
            "approved", []
        )
        if api_key[-20:] not in approved:
            approved.append(api_key[-20:])
    try:
        path.write_text(json.dumps(config, indent=2))
    except Exception:
        logger.exception("failed to seed claude config")

    # the bypass-permissions acceptance lives in global user settings
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            json.loads(settings_path.read_text()) if settings_path.exists() else {}
        )
        if not existing.get("skipDangerousModePermissionPrompt"):
            existing["skipDangerousModePermissionPrompt"] = True
            settings_path.write_text(json.dumps(existing, indent=2))
    except Exception:
        logger.exception("failed to seed global claude settings")

KICKOFF_LINE = (
    "[TREMBLECODE] Session start. Call check_messages, review your standing "
    "context above, then proceed with your role's work."
)


def has_prior_session(workspace: str) -> bool:
    """True if Claude Code already has a conversation for this workspace
    (transcripts live in ~/.claude/projects/<cwd-with-dashes>/). Lets us
    --continue across container/relay restarts despite losing memory."""
    encoded = workspace.replace("/", "-").replace("_", "-").replace(".", "-")
    project_dir = Path.home() / ".claude" / "projects" / encoded
    try:
        return any(project_dir.glob("*.jsonl"))
    except Exception:
        return False


def claude_command(identity_path: str, model: str, effort: str, *, resume: bool) -> str:
    parts = [
        "claude",
        "--dangerously-skip-permissions",
        "--model",
        shlex.quote(model),
        "--effort",
        shlex.quote(effort or "medium"),
        "--append-system-prompt",
        f'"$(cat {shlex.quote(identity_path)})"',
    ]
    if resume:
        parts.append("--continue")
    # keep the pane alive briefly on crash so capture shows the error
    return f'{" ".join(parts)}; echo "[tremblecode] claude exited ($?)"; sleep 5'


async def reconcile_once(client: httpx.AsyncClient) -> None:
    cfg = get_config()
    res = await client.get(
        f"{cfg.server_url}/internal/projects/{cfg.project_id}/agents",
        headers=cfg.server_headers,
        timeout=10,
    )
    res.raise_for_status()
    payload = res.json()
    state.project_status = payload["project_status"]
    state.extra_env = payload.get("extra_env", {})
    desired = {a["name"]: a for a in payload["agents"]}

    # adopt/refresh runtime state
    for name, spec in desired.items():
        rt = state.ensure(name)
        rt.kind = spec["kind"]
        rt.model = spec["model"]
        rt.effort = spec.get("effort", "medium")
        rt.workspace = spec["workspace"] or ""
        rt.tmux_session = spec["tmux_session"] or f"tc-{name}"
        rt.identity_path = spec["identity_path"]

    # remove sessions for agents that no longer exist
    for name in list(state.agents):
        if name not in desired:
            rt = state.agents.pop(name)
            if rt.tmux_session and await tmux.has_session(rt.tmux_session):
                await tmux.kill_session(rt.tmux_session)

    if state.project_status in ("PAUSED", "COMPLETED", "FAILED"):
        return

    for name, spec in desired.items():
        rt = state.agents[name]
        if spec["state"] == "stopped" or not rt.workspace:
            continue
        alive = await tmux.has_session(rt.tmux_session) and await tmux.pane_alive(
            rt.tmux_session
        )
        if alive:
            continue
        # crashed/restarted → continue the conversation; also survives relay
        # restarts (memory lost) by checking for transcripts on disk
        resume = rt.session_started or has_prior_session(rt.workspace)
        if await tmux.has_session(rt.tmux_session):
            await tmux.kill_session(rt.tmux_session)
        logger.info("launching agent %s (resume=%s)", name, resume)
        seed_claude_config(rt.workspace)
        # every (re)launch gets the kickoff line on its session-start hook —
        # resumed conversations also need the nudge to pick work back up
        rt.first_prompt_sent = False
        rt.activity = "unknown"
        ok = await tmux.new_session(
            rt.tmux_session,
            claude_command(rt.identity_path, rt.model, rt.effort, resume=resume),
            cwd=rt.workspace,
            env={
                "TC_AGENT": name,
                "TC_RELAY": f"http://127.0.0.1:{get_config().relay_port}",
                **state.extra_env,  # approved MCP server secrets
            },
        )
        if ok:
            rt.session_started = True


async def deliver_first_prompt(agent_name: str) -> None:
    """Called when the session-start hook fires: the prompt is ready, so the
    kickoff line can be injected safely (never use fixed timers for this)."""
    rt = state.get(agent_name)
    if rt is None or rt.first_prompt_sent:
        return
    rt.first_prompt_sent = True
    await asyncio.sleep(1.0)  # let the TUI finish painting
    if not await tmux.send_line(rt.tmux_session, KICKOFF_LINE):
        rt.first_prompt_sent = False
        logger.warning("kickoff injection failed for %s; will retry", agent_name)


async def reconciler_loop() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await reconcile_once(client)
            except Exception:
                logger.exception("session reconcile failed")
            await asyncio.sleep(10)
