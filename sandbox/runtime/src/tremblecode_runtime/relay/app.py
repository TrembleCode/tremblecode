"""The in-container relay: hook ingest, MCP tool backend, session manager.

Runs on 127.0.0.1:8765. Everything the agents' MCP servers and hook scripts
do goes through here; the relay is the only component that talks to the
orchestrator server (with the internal secret) and to tmux.
"""

import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException, Request

from ..config import get_config
from . import sessions, tmux
from .consumers import consumer_manager
from .state import state

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="tremblecode-relay")

_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=15)
    return _http


async def server_request(method: str, path: str, **kwargs):
    cfg = get_config()
    res = await http().request(
        method, f"{cfg.server_url}{path}", headers=cfg.server_headers, **kwargs
    )
    if res.status_code >= 400:
        raise HTTPException(res.status_code, res.text)
    return res.json()


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(sessions.reconciler_loop())
    asyncio.create_task(consumer_manager())
    logger.info("relay started for project %s", get_config().project_id)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "project": get_config().project_id,
        "agents": {
            name: {"activity": rt.activity, "session": rt.tmux_session}
            for name, rt in state.agents.items()
        },
    }


# ── Hooks ────────────────────────────────────────────────────────


@app.post("/hook/{event}")
async def ingest_hook(event: str, request: Request):
    body = await request.json()
    agent = body.get("agent", "")
    hook_payload = body.get("hook", {}) or {}
    rt = state.get(agent)

    if rt is not None:
        if event in ("busy", "heartbeat"):
            rt.mark("busy")
        elif event == "stop":
            rt.mark("idle")
        elif event == "session-start":
            rt.mark("idle")

    cfg = get_config()
    forward = {
        "agent": agent,
        "event": event,
        "payload": {
            k: hook_payload.get(k)
            for k in ("session_id", "transcript_path", "source", "tool_name", "message", "trigger")
            if hook_payload.get(k) is not None
        },
    }
    # heartbeats stay local (state only) to keep traffic down
    if event != "heartbeat":
        try:
            await server_request(
                "POST", f"/internal/projects/{cfg.project_id}/hooks", json=forward
            )
        except Exception:
            logger.warning("hook forward failed (%s/%s)", agent, event)

    response: dict = {}
    if event == "session-start":
        # standing context re-injection — rebuilt from DB, survives /clear
        try:
            ctx = await server_request(
                "GET",
                f"/internal/projects/{cfg.project_id}/agents/{agent}/context",
            )
            response = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": ctx["context"],
                }
            }
        except Exception:
            logger.warning("context fetch failed for %s", agent)
        # the prompt is ready now — safe moment for the kickoff line
        asyncio.create_task(sessions.deliver_first_prompt(agent))
    elif event == "pre-compact":
        response = {
            "systemMessage": (
                "Compacting. Preserve: current task id/branch/acceptance "
                "criteria, unacked messages, decisions made, files touched. "
                "Drop: tool transcripts and exploration dead ends."
            )
        }
    elif event == "stop":
        transcript = hook_payload.get("transcript_path")
        if transcript:
            from .transcripts import report_costs

            asyncio.create_task(report_costs(agent, transcript))

    return response


# ── MCP backend: messaging ───────────────────────────────────────


@app.post("/messages/send")
async def send_message(request: Request):
    body = await request.json()
    cfg = get_config()
    return await server_request(
        "POST", f"/internal/projects/{cfg.project_id}/messages", json=body
    )


@app.get("/messages/pending")
async def pending_messages(agent: str, limit: int = 20):
    cfg = get_config()
    return await server_request(
        "GET",
        f"/internal/projects/{cfg.project_id}/messages/pending",
        params={"agent": agent, "limit": limit},
    )


@app.post("/messages/{msg_id}/ack")
async def ack_message(msg_id: str, request: Request):
    body = await request.json()
    return await server_request("POST", f"/internal/messages/{msg_id}/ack", json=body)


@app.post("/status")
async def report_status(request: Request):
    body = await request.json()
    cfg = get_config()
    rt = state.get(body.get("agent", ""))
    if rt is not None and body.get("state") in ("idle", "working"):
        rt.mark("idle" if body["state"] == "idle" else "busy")
    return await server_request(
        "POST", f"/internal/projects/{cfg.project_id}/status", json=body
    )


@app.get("/team")
async def team():
    cfg = get_config()
    data = await server_request(
        "GET", f"/internal/projects/{cfg.project_id}/agents"
    )
    return {
        "agents": [
            {
                "name": a["name"],
                "role_key": a["role_key"],
                "kind": a["kind"],
                "model": a["model"],
                "state": a["state"],
            }
            for a in data["agents"]
        ]
    }


@app.get("/project-info")
async def project_info():
    cfg = get_config()
    return await server_request(
        "GET", f"/internal/projects/{cfg.project_id}/info"
    )


# Generic authenticated passthrough for tool families added later
# (tasks, plan, escalations, services). Keeps the MCP server thin.
@app.post("/server{path:path}")
async def server_proxy_post(path: str, request: Request):
    body = await request.json()
    cfg = get_config()
    full = path.replace("{project_id}", cfg.project_id)
    return await server_request("POST", f"/internal{full}", json=body)


@app.get("/server{path:path}")
async def server_proxy_get(path: str, request: Request):
    cfg = get_config()
    full = path.replace("{project_id}", cfg.project_id)
    return await server_request(
        "GET", f"/internal{full}", params=dict(request.query_params)
    )
