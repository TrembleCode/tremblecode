import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..models import McpSuggestion, Project
from ..schemas.core import OrmModel
from ..services import bus, provisioner
from ..services.secrets import encrypt
from ..ws.manager import manager
from .deps import SessionDep

router = APIRouter(prefix="/api", tags=["mcp"])


class McpSuggestionOut(OrmModel):
    id: str
    project_id: str
    name: str
    transport: str
    command: str
    args: list
    env_keys: list
    reason: str
    status: str
    created_at: datetime


@router.get(
    "/projects/{project_id}/mcp-suggestions", response_model=list[McpSuggestionOut]
)
async def list_suggestions(project_id: str, session: SessionDep):
    rows = await session.scalars(
        select(McpSuggestion).where(McpSuggestion.project_id == project_id)
    )
    return list(rows)


async def _apply_approved(session, project: Project) -> None:
    """Re-render .mcp.json with all approved servers, then ask every agent's
    consumer to restart its session at the next idle moment (claude
    --continue re-reads the MCP config)."""
    approved = list(
        await session.scalars(
            select(McpSuggestion).where(
                McpSuggestion.project_id == project.id,
                McpSuggestion.status.in_(["approved", "installed"]),
            )
        )
    )
    provisioner.render_mcp_json(project, approved)
    for suggestion in approved:
        suggestion.status = "installed"
    await session.commit()
    try:
        await bus.publish(
            project.id,
            {
                "type": "restart",
                "to": "broadcast",
                "reason": "mcp servers updated — session will resume automatically",
            },
        )
    except Exception:
        pass


class ApproveIn(BaseModel):
    env_values: dict[str, str] = {}


@router.post("/mcp-suggestions/{suggestion_id}/approve", response_model=McpSuggestionOut)
async def approve_suggestion(
    suggestion_id: str, payload: ApproveIn, session: SessionDep
):
    suggestion = await session.get(McpSuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(404, "suggestion not found")
    if suggestion.status not in ("proposed", "rejected"):
        raise HTTPException(409, f"suggestion is {suggestion.status}")
    missing = [k for k in suggestion.env_keys if not payload.env_values.get(k)]
    if missing:
        raise HTTPException(422, f"missing env values: {', '.join(missing)}")
    if payload.env_values:
        suggestion.env_values_encrypted = encrypt(json.dumps(payload.env_values))
    suggestion.status = "approved"
    await session.commit()

    project = await session.get(Project, suggestion.project_id)
    if project.host_dir:
        await _apply_approved(session, project)
    await manager.broadcast(
        "mcp.updated", suggestion.project_id, {"name": suggestion.name}
    )
    return suggestion


@router.post("/mcp-suggestions/{suggestion_id}/reject", response_model=McpSuggestionOut)
async def reject_suggestion(suggestion_id: str, session: SessionDep):
    suggestion = await session.get(McpSuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(404, "suggestion not found")
    suggestion.status = "rejected"
    await session.commit()
    await manager.broadcast(
        "mcp.updated", suggestion.project_id, {"name": suggestion.name}
    )
    return suggestion
