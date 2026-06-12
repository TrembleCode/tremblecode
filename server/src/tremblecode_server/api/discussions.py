from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import Discussion, DiscussionMessage, Project
from ..schemas.core import OrmModel
from ..services import discussion_service
from .deps import SessionDep

router = APIRouter(prefix="/api/projects/{project_id}/discussion", tags=["discussion"])


class DiscussionMessageOut(OrmModel):
    id: str
    role: str
    content: str
    created_at: datetime


class PostIn(BaseModel):
    content: str


async def _project(session, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return project


@router.get("", response_model=list[DiscussionMessageOut])
async def get_discussion(project_id: str, session: SessionDep):
    discussion = await session.scalar(
        select(Discussion).where(Discussion.project_id == project_id)
    )
    if not discussion:
        return []
    rows = await session.scalars(
        select(DiscussionMessage)
        .where(DiscussionMessage.discussion_id == discussion.id)
        .order_by(DiscussionMessage.created_at)
    )
    return list(rows)


@router.post("/messages", response_model=DiscussionMessageOut)
async def post_message(project_id: str, payload: PostIn, session: SessionDep):
    project = await _project(session, project_id)
    return await discussion_service.post_message(session, project, payload.content)


@router.post("/finalize")
async def finalize(project_id: str, session: SessionDep):
    project = await _project(session, project_id)
    prd = await discussion_service.finalize(session, project)
    return {"prd_md": prd}
