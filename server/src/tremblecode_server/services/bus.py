"""Redis stream helpers. The stream is a doorbell + redelivery layer only —
message bodies live in SQLite. One stream per project; one consumer group per
agent (created by the in-container relay)."""

import redis.asyncio as aioredis

from ..config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def stream_key(project_id: str) -> str:
    return f"tc:msg:{project_id}"


async def publish(project_id: str, entry: dict) -> str:
    """Add an entry to the project stream. Entry values must be strings."""
    return await get_redis().xadd(
        stream_key(project_id), {k: str(v) for k, v in entry.items()}
    )


async def publish_message_notification(
    project_id: str, *, msg_id: str, to: str, frm: str
) -> str:
    return await publish(
        project_id, {"type": "message", "msg_id": msg_id, "to": to, "from": frm}
    )


async def publish_ack_receipt(
    project_id: str, *, msg_id: str, to: str, acked_by: str, note: str = ""
) -> str:
    return await publish(
        project_id,
        {
            "type": "ack_receipt",
            "msg_id": msg_id,
            "to": to,
            "acked_by": acked_by,
            "note": note[:200],
        },
    )
