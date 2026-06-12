from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..database import SessionLocal
from ..models import Project, ProjectAgent
from ..services.terminal_bridge import bridge_terminal
from ..ws.manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Clients don't need to send anything; keep the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)


@router.websocket("/ws/terminal/{agent_id}")
async def terminal_endpoint(ws: WebSocket, agent_id: str, mode: str = "ro"):
    async with SessionLocal() as session:
        agent = await session.get(ProjectAgent, agent_id)
        project = await session.get(Project, agent.project_id) if agent else None
    if not agent or not project:
        await ws.accept()
        await ws.send_text("\r\n[tremblecode] unknown agent\r\n")
        await ws.close()
        return
    await bridge_terminal(
        ws,
        slug=project.slug,
        tmux_session=agent.tmux_session or f"tc-{agent.name}",
        read_only=(mode != "rw"),
    )
