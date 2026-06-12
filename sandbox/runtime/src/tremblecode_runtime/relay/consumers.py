"""Per-agent Redis stream consumers.

Reliability model:
- one consumer group per agent on the project stream; the doorbell entry is
  XACKed only AFTER the notify line was verifiably injected into the agent's
  tmux pane (transport ack);
- if the agent is busy the entry stays pending; the Stop hook sets the wake
  event and pending entries are re-driven via XAUTOCLAIM;
- a sweeper periodically reclaims entries from dead consumers (relay restart).
Application-level acks (ack_message) are handled by the server.
"""

import asyncio
import logging
import time

import httpx
import redis.asyncio as aioredis

from ..config import get_config
from . import tmux
from .state import state
from .state import AgentRuntimeState

logger = logging.getLogger(__name__)

CONSUMER = "relay"

# If hooks have been silent this long, trust the pane over the hook state.
# Covers stuck-busy (e.g. a submission that never produced a Stop hook).
HOOK_STALE_SECONDS = 45


def effectively_idle(rt: AgentRuntimeState) -> bool:
    if rt.is_idle:
        return True
    return (time.time() - rt.last_hook_at) > HOOK_STALE_SECONDS


def group_for(agent: str) -> str:
    return f"cg:{agent}"


async def ensure_group(r: aioredis.Redis, agent: str) -> None:
    cfg = get_config()
    try:
        await r.xgroup_create(cfg.stream_key, group_for(agent), id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _notify_line(entry: dict) -> str | None:
    """One short line; bodies travel via MCP check_messages."""
    kind = entry.get("type", "message")
    if kind == "message":
        return (
            f"[TREMBLECODE] New message from {entry.get('from', '?')} "
            f"(id {entry.get('msg_id', '?')[:8]}). Run check_messages now."
        )
    if kind == "ack_receipt":
        note = entry.get("note", "")
        if not note:
            # a bare ack isn't worth a full agent turn — it's visible in the
            # DB/UI, and the watchdog still chases genuinely unacked messages
            return None
        return (
            f"[TREMBLECODE] Your message {entry.get('msg_id', '?')[:8]} was "
            f'acknowledged by {entry.get("acked_by", "?")} — note: "{note}".'
        )
    if kind == "nudge":
        return f"[TREMBLECODE] {entry.get('text', 'Check your pending work.')}"
    return None


async def _mark_notified(client: httpx.AsyncClient, msg_ids: list[str]) -> None:
    cfg = get_config()
    try:
        await client.post(
            f"{cfg.server_url}/internal/projects/{cfg.project_id}/messages/notified",
            json={"msg_ids": msg_ids},
            headers=cfg.server_headers,
            timeout=5,
        )
    except Exception:
        logger.warning("failed to mark %s notified", msg_ids)


async def _try_deliver(
    client: httpx.AsyncClient, agent: str, entry: dict
) -> bool:
    """Inject the notify line if the agent is idle at the prompt. Returns
    True when the entry can be acked."""
    rt = state.get(agent)
    if rt is None or not rt.tmux_session:
        return False
    if entry.get("to") not in (agent, "broadcast"):
        return True  # not for us — ack and move on
    if not effectively_idle(rt):
        return False
    pane = await tmux.capture_pane(rt.tmux_session)
    if not tmux.looks_idle(pane):
        return False
    if entry.get("type") == "restart":
        # graceful at-idle restart: kill the session; the reconciler relaunches
        # with --continue (conversation + fresh .mcp.json / env)
        logger.info("restarting session for %s: %s", agent, entry.get("reason", ""))
        await tmux.kill_session(rt.tmux_session)
        rt.activity = "unknown"
        rt.first_prompt_sent = False  # re-kickoff after relaunch so work resumes
        return True
    if entry.get("type") == "clear":
        # context policy: fresh context per task. /clear is a user-level
        # command, so the relay types it; the SessionStart(clear) hook then
        # re-injects standing context and the kickoff line resumes work.
        logger.info("clearing context for %s: %s", agent, entry.get("reason", ""))
        rt.first_prompt_sent = False
        if not await tmux.send_line(rt.tmux_session, "/clear"):
            rt.first_prompt_sent = True
            return False
        return True
    if entry.get("type") == "set_effort":
        # /effort works mid-session and persists for relaunches via the
        # desired-state --effort flag (the server updates the DB first)
        level = entry.get("level", "")
        if level not in ("low", "medium", "high", "xhigh", "max"):
            logger.warning("ignoring set_effort with level %r for %s", level, agent)
            return True
        logger.info("setting effort for %s: %s", agent, level)
        return await tmux.send_line(rt.tmux_session, f"/effort {level}")
    if entry.get("type") == "set_model":
        model = entry.get("model", "")
        if not model:
            return True
        logger.info("setting model for %s: %s", agent, model)
        return await tmux.send_line(rt.tmux_session, f"/model {model}")
    line = _notify_line(entry)
    if line is None:
        return True
    if not await tmux.send_line(rt.tmux_session, line):
        return False
    if entry.get("type") == "message" and entry.get("msg_id"):
        await _mark_notified(client, [entry["msg_id"]])
    return True


def _coalesced_line(entries: list[dict]) -> str:
    if len(entries) == 1:
        return _notify_line(entries[0])
    senders: list[str] = []
    for entry in entries:
        frm = entry.get("from", "?")
        if frm not in senders:
            senders.append(frm)
    return (
        f"[TREMBLECODE] {len(entries)} new messages from "
        f"{', '.join(senders)}. Run check_messages now."
    )


async def _flush_message_group(
    client: httpx.AsyncClient, agent: str, entries: list[dict]
) -> bool:
    """Inject ONE coalesced notify line for buffered message entries — each
    avoided wake-up saves a full agent turn."""
    if not entries:
        return True
    rt = state.get(agent)
    if rt is None or not rt.tmux_session:
        return False
    if not effectively_idle(rt):
        return False
    pane = await tmux.capture_pane(rt.tmux_session)
    if not tmux.looks_idle(pane):
        return False
    if not await tmux.send_line(rt.tmux_session, _coalesced_line(entries)):
        return False
    msg_ids = [e.get("msg_id") for e in entries if e.get("msg_id")]
    if msg_ids:
        await _mark_notified(client, msg_ids)
    return True


async def _drain_entries(
    r: aioredis.Redis,
    client: httpx.AsyncClient,
    agent: str,
    group: str,
    entries: list,
) -> bool:
    """Deliver a batch in stream order, coalescing consecutive message
    entries into a single notify line. Control entries (clear, restart,
    set_effort, ...) are barriers: buffered messages flush before them.
    Delivered entries are XACKed; on the first stalled delivery the rest
    stay pending for the next idle re-drive."""
    cfg = get_config()
    buffer: list[tuple[str, dict]] = []

    async def flush() -> bool:
        if not buffer:
            return True
        if not await _flush_message_group(client, agent, [f for _, f in buffer]):
            return False
        for entry_id, _ in buffer:
            await r.xack(cfg.stream_key, group, entry_id)
        buffer.clear()
        return True

    for entry_id, fields in entries:
        if fields.get("to") not in (agent, "broadcast"):
            await r.xack(cfg.stream_key, group, entry_id)  # not for us
            continue
        if fields.get("type", "message") == "message":
            buffer.append((entry_id, fields))
            continue
        if not await flush():
            return False
        if not await _try_deliver(client, agent, fields):
            return False
        await r.xack(cfg.stream_key, group, entry_id)
    return await flush()


async def consumer_loop(agent: str) -> None:
    cfg = get_config()
    # socket_timeout=None: redis-py 8 defaults to a 5s read timeout, which
    # races XREADGROUP BLOCK and kills the consumer with TimeoutError
    r = aioredis.from_url(cfg.redis_url, decode_responses=True, socket_timeout=None)
    client = httpx.AsyncClient()
    await ensure_group(r, agent)
    group = group_for(agent)
    logger.info("consumer started for %s", agent)

    try:
        while agent in state.agents:
            rt = state.agents[agent]
            try:
                # 1) re-drive our own pending entries when idle
                if effectively_idle(rt):
                    _, claimed, *_ = await r.xautoclaim(
                        cfg.stream_key, group, CONSUMER, min_idle_time=0, count=10
                    )
                    if claimed:
                        await _drain_entries(r, client, agent, group, claimed)

                # 2) read new entries
                resp = await r.xreadgroup(
                    group, CONSUMER, {cfg.stream_key: ">"}, count=10, block=5000
                )
                for _stream, entries in resp or []:
                    # stalled deliveries stay pending; stop hook re-drives
                    await _drain_entries(r, client, agent, group, entries)

                rt.wake.clear()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("consumer error for %s", agent)
                await asyncio.sleep(3)
    finally:
        await client.aclose()
        await r.aclose()
        logger.info("consumer stopped for %s", agent)


async def consumer_manager() -> None:
    """Keeps one consumer task per known agent."""
    tasks: dict[str, asyncio.Task] = {}
    while True:
        for name in list(state.agents):
            task = tasks.get(name)
            if task is None or task.done():
                tasks[name] = asyncio.create_task(consumer_loop(name))
        for name in list(tasks):
            if name not in state.agents:
                tasks.pop(name).cancel()
        await asyncio.sleep(5)
