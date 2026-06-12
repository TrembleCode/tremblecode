from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..models import AgentTemplate
from ..schemas.core import AgentTemplateCreate, AgentTemplateOut, AgentTemplateUpdate
from .deps import SessionDep

router = APIRouter(prefix="/api/agent-templates", tags=["roster"])


@router.get("", response_model=list[AgentTemplateOut])
async def list_templates(session: SessionDep):
    rows = await session.scalars(select(AgentTemplate).order_by(AgentTemplate.created_at))
    return list(rows)


@router.post("", response_model=AgentTemplateOut, status_code=201)
async def create_template(payload: AgentTemplateCreate, session: SessionDep):
    existing = await session.scalar(
        select(AgentTemplate).where(AgentTemplate.role_key == payload.role_key)
    )
    if existing:
        raise HTTPException(409, f"role_key '{payload.role_key}' already exists")
    tpl = AgentTemplate(**payload.model_dump())
    session.add(tpl)
    await session.commit()
    return tpl


@router.get("/{template_id}", response_model=AgentTemplateOut)
async def get_template(template_id: str, session: SessionDep):
    tpl = await session.get(AgentTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "template not found")
    return tpl


@router.patch("/{template_id}", response_model=AgentTemplateOut)
async def update_template(
    template_id: str, payload: AgentTemplateUpdate, session: SessionDep
):
    tpl = await session.get(AgentTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "template not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, key, value)
    await session.commit()
    return tpl


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str, session: SessionDep):
    tpl = await session.get(AgentTemplate, template_id)
    if not tpl:
        raise HTTPException(404, "template not found")
    if tpl.is_builtin:
        raise HTTPException(400, "builtin templates cannot be deleted")
    await session.delete(tpl)
    await session.commit()
