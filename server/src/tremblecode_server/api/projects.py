from fastapi import APIRouter, HTTPException
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import AgentTemplate, Project, ProjectStatus
from ..services import lifecycle
from ..schemas.core import (
    PrdUpdate,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)
from ..ws.manager import manager
from .deps import SessionDep

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _unique_slug(session, name: str) -> str:
    base = slugify(name) or "project"
    slug = base
    n = 2
    while await session.scalar(select(Project).where(Project.slug == slug)):
        slug = f"{base}-{n}"
        n += 1
    return slug


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: SessionDep):
    rows = await session.scalars(select(Project).order_by(Project.created_at.desc()))
    return list(rows)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(payload: ProjectCreate, session: SessionDep):
    roster = [entry.model_dump() for entry in payload.roster]
    if not roster:
        templates = await session.scalars(select(AgentTemplate))
        roster = [
            {"role_key": t.role_key, "count": t.default_count, "model": None}
            for t in templates
        ]
    status = (
        ProjectStatus.DISCUSSION
        if payload.start_with_discussion and not payload.prd_md
        else ProjectStatus.DRAFT
    )
    project = Project(
        name=payload.name,
        slug=await _unique_slug(session, payload.name),
        description=payload.description,
        prd_md=payload.prd_md,
        status=status,
        image_variant=payload.image_variant,
        config_json={"roster": roster, "ports": {}},
    )
    session.add(project)
    await session.commit()
    await manager.broadcast("project.created", project.id, {"slug": project.slug})
    return project


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(project_id: str, session: SessionDep):
    project = await session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.agents))
    )
    if not project:
        raise HTTPException(404, "project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: str, payload: ProjectUpdate, session: SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await session.commit()
    await manager.broadcast("project.updated", project.id, {"status": project.status})
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, session: SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    await session.delete(project)
    await session.commit()
    await manager.broadcast("project.deleted", project_id, {})


async def _get_or_404(session, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return project


@router.post("/{project_id}/start", response_model=ProjectOut)
async def start_project(project_id: str, session: SessionDep):
    project = await _get_or_404(session, project_id)
    return await lifecycle.start_project(session, project)


@router.post("/{project_id}/pause", response_model=ProjectOut)
async def pause_project(project_id: str, session: SessionDep):
    project = await _get_or_404(session, project_id)
    return await lifecycle.pause_project(session, project)


@router.post("/{project_id}/resume", response_model=ProjectOut)
async def resume_project(project_id: str, session: SessionDep):
    project = await _get_or_404(session, project_id)
    return await lifecycle.resume_project(session, project)


@router.get("/{project_id}/prd")
async def get_prd(project_id: str, session: SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return {"prd_md": project.prd_md}


@router.put("/{project_id}/prd", response_model=ProjectOut)
async def put_prd(project_id: str, payload: PrdUpdate, session: SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    project.prd_md = payload.prd_md
    if project.status == ProjectStatus.DISCUSSION and payload.prd_md:
        project.status = ProjectStatus.DRAFT
    await session.commit()
    await manager.broadcast("project.updated", project.id, {"prd": True})
    return project
