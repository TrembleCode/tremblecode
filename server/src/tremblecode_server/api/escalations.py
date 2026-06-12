from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import Escalation, EscalationStatus, Service
from ..schemas.core import OrmModel
from ..services import escalation_service
from .deps import SessionDep

router = APIRouter(prefix="/api", tags=["escalations"])


class EscalationOut(OrmModel):
    id: str
    project_id: str
    agent_name: str
    type: str
    topic: str
    body_md: str
    options: list
    blocking: bool
    status: str
    response_md: str | None
    created_at: datetime
    responded_at: datetime | None


@router.get("/inbox", response_model=list[EscalationOut])
async def global_inbox(session: SessionDep, status: str = "open"):
    query = select(Escalation).order_by(Escalation.created_at.desc())
    if status:
        query = query.where(Escalation.status == status)
    return list(await session.scalars(query))


@router.get("/projects/{project_id}/escalations", response_model=list[EscalationOut])
async def project_escalations(project_id: str, session: SessionDep, status: str = ""):
    query = select(Escalation).where(Escalation.project_id == project_id)
    if status:
        query = query.where(Escalation.status == status)
    return list(await session.scalars(query.order_by(Escalation.created_at.desc())))


class RespondIn(BaseModel):
    response: str = ""
    option: str | None = None


@router.post("/escalations/{escalation_id}/respond", response_model=EscalationOut)
async def respond(escalation_id: str, payload: RespondIn, session: SessionDep):
    escalation = await session.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(404, "escalation not found")
    await escalation_service.respond(
        session, escalation, payload.response, payload.option
    )
    return escalation


@router.post("/escalations/{escalation_id}/dismiss", response_model=EscalationOut)
async def dismiss(escalation_id: str, session: SessionDep):
    escalation = await session.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(404, "escalation not found")
    escalation.status = EscalationStatus.DISMISSED
    await session.commit()
    return escalation


class ServiceOut(OrmModel):
    id: str
    name: str
    agent_name: str
    container_port: int
    host_port: int
    status: str


@router.get("/projects/{project_id}/services", response_model=list[ServiceOut])
async def project_services(project_id: str, session: SessionDep):
    return list(
        await session.scalars(select(Service).where(Service.project_id == project_id))
    )


@router.get("/projects/{project_id}/costs")
async def project_costs(project_id: str, session: SessionDep):
    from ..services import cost_service

    return await cost_service.project_summary(session, project_id)
