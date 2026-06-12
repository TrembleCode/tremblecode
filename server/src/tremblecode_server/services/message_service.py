import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, MessageStatus
from ..ws.manager import manager
from . import bus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_message(
    session: AsyncSession,
    *,
    project_id: str,
    from_participant: str,
    to_participant: str,
    body_md: str,
    subject: str = "",
    thread_id: str | None = None,
    ack_requested: bool = False,
    priority: str = "normal",
    task_key: str | None = None,
) -> Message:
    """Persist a message and ring the doorbell on the project stream."""
    message = Message(
        project_id=project_id,
        from_participant=from_participant,
        to_participant=to_participant,
        subject=subject,
        body_md=body_md,
        thread_id=thread_id,
        ack_requested=ack_requested,
        priority=priority,
        task_key=task_key,
    )
    session.add(message)
    await session.commit()

    # human-bound messages don't need a doorbell — the UI sees them via WS
    if to_participant != "human":
        try:
            message.redis_id = await bus.publish_message_notification(
                project_id,
                msg_id=message.id,
                to=to_participant,
                frm=from_participant,
            )
            await session.commit()
        except Exception:
            logger.exception("failed to publish doorbell for %s", message.id)

    await manager.broadcast(
        "message.new",
        project_id,
        {
            "id": message.id,
            "from": from_participant,
            "to": to_participant,
            "subject": subject,
            "ack_requested": ack_requested,
        },
    )
    return message


async def pending_for_agent(
    session: AsyncSession, project_id: str, agent_name: str, limit: int = 20
) -> list[Message]:
    """Undelivered messages for an agent; marks them delivered. Broadcasts
    track delivery per recipient so every agent gets them exactly once."""
    rows = list(
        await session.scalars(
            select(Message)
            .where(
                Message.project_id == project_id,
                Message.status.in_(
                    [
                        MessageStatus.QUEUED,
                        MessageStatus.NOTIFIED,
                        MessageStatus.DELIVERED,
                    ]
                ),
                Message.to_participant.in_([agent_name, "broadcast"]),
            )
            .order_by(Message.created_at)
            .limit(limit * 3)
        )
    )
    result: list[Message] = []
    for message in rows:
        if message.to_participant == "broadcast":
            if agent_name in (message.delivered_to or []):
                continue
            message.delivered_to = [*(message.delivered_to or []), agent_name]
            message.status = MessageStatus.DELIVERED
            message.delivered_at = message.delivered_at or _now()
        else:
            if message.status == MessageStatus.DELIVERED:
                continue
            message.status = MessageStatus.DELIVERED
            message.delivered_at = _now()
        result.append(message)
        if len(result) >= limit:
            break
    rows = result
    await session.commit()
    if rows:
        await manager.broadcast(
            "message.delivered",
            project_id,
            {"ids": [m.id for m in rows], "agent": agent_name},
        )
    return rows


async def mark_notified(session: AsyncSession, msg_id: str) -> None:
    message = await session.get(Message, msg_id)
    if message and message.status == MessageStatus.QUEUED:
        message.status = MessageStatus.NOTIFIED
        message.notified_at = _now()
        await session.commit()


async def ack_message(
    session: AsyncSession, msg_id: str, acked_by: str, note: str = ""
) -> Message | None:
    message = await session.get(Message, msg_id)
    if not message:
        return None
    message.status = MessageStatus.ACKED
    message.acked_at = _now()
    message.ack_note = note
    await session.commit()

    # route the receipt back to the sender (agents only; humans see WS/UI)
    if message.ack_requested and message.from_participant != "human":
        try:
            await bus.publish_ack_receipt(
                message.project_id,
                msg_id=message.id,
                to=message.from_participant,
                acked_by=acked_by,
                note=note,
            )
        except Exception:
            logger.exception("failed to publish ack receipt for %s", message.id)

    await manager.broadcast(
        "message.acked",
        message.project_id,
        {"id": message.id, "by": acked_by, "note": note},
    )
    return message
