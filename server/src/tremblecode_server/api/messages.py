from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import Message, Project
from ..schemas.core import OrmModel
from ..services import message_service
from .deps import SessionDep
from datetime import datetime

router = APIRouter(prefix="/api/projects/{project_id}/messages", tags=["messages"])


class MessageCreate(BaseModel):
    to: str
    body_md: str
    subject: str = ""
    thread_id: str | None = None
    ack_requested: bool = False
    priority: str = "normal"


class MessageOut(OrmModel):
    id: str
    project_id: str
    from_participant: str
    to_participant: str
    thread_id: str | None
    subject: str
    body_md: str
    priority: str
    ack_requested: bool
    status: str
    task_key: str | None
    created_at: datetime
    delivered_at: datetime | None
    acked_at: datetime | None
    ack_note: str


@router.get("", response_model=list[MessageOut])
async def list_messages(
    project_id: str,
    session: SessionDep,
    participant: str | None = None,
    thread_id: str | None = None,
    limit: int = 200,
):
    query = select(Message).where(Message.project_id == project_id)
    if participant:
        query = query.where(
            (Message.from_participant == participant)
            | (Message.to_participant == participant)
        )
    if thread_id:
        query = query.where(Message.thread_id == thread_id)
    rows = await session.scalars(query.order_by(Message.created_at.desc()).limit(limit))
    return list(reversed(list(rows)))


@router.post("", response_model=MessageOut, status_code=201)
async def send_message(project_id: str, payload: MessageCreate, session: SessionDep):
    """Human → agent message; rides the same bus as agent↔agent traffic."""
    if not await session.get(Project, project_id):
        raise HTTPException(404, "project not found")
    return await message_service.create_message(
        session,
        project_id=project_id,
        from_participant="human",
        to_participant=payload.to,
        body_md=payload.body_md,
        subject=payload.subject,
        thread_id=payload.thread_id,
        ack_requested=payload.ack_requested,
        priority=payload.priority,
    )
