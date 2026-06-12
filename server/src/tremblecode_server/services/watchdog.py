"""Background reliability loop:
- nudges agents about ack-requested messages that sit unacked past the
  timeout (up to ack_max_nudges), then opens a stuck_agent escalation;
- marks agents stale-idle if their hooks went silent.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal
from ..models import Escalation, Message, MessageStatus
from ..ws.manager import manager
from . import bus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _check_unacked() -> None:
    settings = get_settings()
    timeout = timedelta(seconds=settings.ack_timeout_seconds)
    async with SessionLocal() as session:
        rows = list(
            await session.scalars(
                select(Message).where(
                    Message.ack_requested.is_(True),
                    Message.status.in_(
                        [
                            MessageStatus.QUEUED,
                            MessageStatus.NOTIFIED,
                            MessageStatus.DELIVERED,
                        ]
                    ),
                    Message.to_participant != "human",
                )
            )
        )
        for message in rows:
            created = message.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            overdue_factor = message.nudge_count + 1
            if _now() - created < timeout * overdue_factor:
                continue
            if message.nudge_count < settings.ack_max_nudges:
                message.nudge_count += 1
                await session.commit()
                try:
                    await bus.publish(
                        message.project_id,
                        {
                            "type": "nudge",
                            "to": message.to_participant,
                            "text": (
                                f"REMINDER: message {message.id[:8]} from "
                                f"{message.from_participant} is still waiting for "
                                "your ack. Run check_messages and ack_message now."
                            ),
                        },
                    )
                except Exception:
                    logger.exception("nudge publish failed")
            else:
                # exhausted nudges → human inbox
                existing = await session.scalar(
                    select(Escalation).where(
                        Escalation.ref_id == message.id,
                        Escalation.type == "stuck_agent",
                    )
                )
                if existing:
                    continue
                session.add(
                    Escalation(
                        project_id=message.project_id,
                        agent_name="system",
                        type="stuck_agent",
                        topic=f"Agent {message.to_participant} is not responding",
                        body_md=(
                            f"Message `{message.id[:8]}` from "
                            f"`{message.from_participant}` (subject: "
                            f"\"{message.subject or '—'}\") has been waiting for an "
                            f"ack since {created.isoformat()} despite "
                            f"{message.nudge_count} nudges.\n\n> "
                            + message.body_md[:500]
                        ),
                        blocking=False,
                        ref_id=message.id,
                    )
                )
                message.status = MessageStatus.EXPIRED
                await session.commit()
                await manager.broadcast(
                    "escalation.new",
                    message.project_id,
                    {"type": "stuck_agent", "agent": message.to_participant},
                )


async def watchdog_loop() -> None:
    while True:
        try:
            await _check_unacked()
        except Exception:
            logger.exception("watchdog iteration failed")
        await asyncio.sleep(60)
