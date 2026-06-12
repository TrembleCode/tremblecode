"""Cost/usage extraction from Claude Code transcript JSONL files.

On every Stop hook the relay reads the session transcript from its persisted
byte offset, extracts `message.usage` from new assistant events, and reports
deltas to the server. Offsets are keyed by transcript path and stored under
the project's .tremblecode dir, so relay/container restarts never double-count
(the server additionally dedups on (session_id, offset)).

Claude Code writes one transcript line per assistant content block, each
repeating the same `message.usage` for that API response. Usage is counted
once per (message.id, requestId); the last-seen pair is persisted with the
offset because a response's duplicate lines may straddle two reads."""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx

from ..config import get_config

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()


def _offsets_path() -> Path:
    return Path(get_config().project_dir) / ".tremblecode" / "transcript-offsets.json"


def _load_offsets() -> dict:
    try:
        return json.loads(_offsets_path().read_text())
    except Exception:
        return {}


def _save_offsets(offsets: dict) -> None:
    path = _offsets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(offsets))


def _extract_events(
    path: str, start: int, last_message_id: str | None
) -> tuple[list[dict], int, str | None]:
    events: list[dict] = []
    with open(path, "rb") as f:
        f.seek(start)
        offset = start
        for raw_line in f:
            line_offset = offset
            offset += len(raw_line)
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            message = record.get("message") or {}
            usage = message.get("usage")
            if record.get("type") != "assistant" or not usage:
                continue
            message_id = f"{message.get('id')}:{record.get('requestId')}"
            if message.get("id") and message_id == last_message_id:
                continue  # duplicate line of an already-counted API response
            last_message_id = message_id
            events.append(
                {
                    "transcript_offset": line_offset,
                    "claude_session_id": record.get("sessionId", ""),
                    "model": message.get("model", ""),
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cache_creation_tokens": usage.get(
                        "cache_creation_input_tokens", 0
                    ),
                    "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                }
            )
        return events, offset, last_message_id


async def report_costs(agent: str, transcript_path: str | None) -> None:
    if not transcript_path or not os.path.exists(transcript_path):
        return
    cfg = get_config()
    async with _lock:
        offsets = _load_offsets()
        entry = offsets.get(transcript_path, 0)
        if isinstance(entry, int):  # legacy format: bare byte offset
            entry = {"offset": entry, "last_message_id": None}
        try:
            events, new_offset, last_message_id = await asyncio.to_thread(
                _extract_events,
                transcript_path,
                entry["offset"],
                entry["last_message_id"],
            )
        except Exception:
            logger.exception("transcript parse failed for %s", transcript_path)
            return
        new_entry = {"offset": new_offset, "last_message_id": last_message_id}
        if not events:
            offsets[transcript_path] = new_entry
            _save_offsets(offsets)
            return
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{cfg.server_url}/internal/projects/{cfg.project_id}/costs",
                    json={"agent": agent, "events": events},
                    headers=cfg.server_headers,
                    timeout=15,
                )
                res.raise_for_status()
        except Exception:
            logger.exception("cost report failed — offset NOT advanced (will retry)")
            return
        offsets[transcript_path] = new_entry
        _save_offsets(offsets)
