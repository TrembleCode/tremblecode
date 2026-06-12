"""WebSocket ⇄ docker exec PTY ⇄ tmux attach bridge.

The browser's xterm.js connects to /ws/terminal/{agent_id}; we exec
`tmux attach` inside the project container with a TTY and pump bytes both
ways. tmux multiplexing means this coexists with the relay's send-keys and
other viewers. Read-only mode attaches with `-r`.
"""

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from . import docker_service

logger = logging.getLogger(__name__)


async def bridge_terminal(
    ws: WebSocket, *, slug: str, tmux_session: str, read_only: bool
) -> None:
    await ws.accept()
    client = docker_service.client()
    api = client.api

    attach_cmd = ["tmux", "attach-session", "-t", f"={tmux_session}"]
    if read_only:
        attach_cmd.append("-r")

    try:
        exec_id = api.exec_create(
            docker_service.container_name(slug),
            attach_cmd,
            tty=True,
            stdin=True,
            user="agent",
            environment={"TERM": "xterm-256color"},
        )["Id"]
        sock = api.exec_start(exec_id, tty=True, socket=True)
        raw = sock._sock  # the underlying socket for non-blocking IO
        raw.setblocking(False)
    except Exception as exc:
        logger.exception("terminal attach failed")
        await ws.send_text(f"\r\n[tremblecode] attach failed: {exc}\r\n")
        await ws.close()
        return

    loop = asyncio.get_event_loop()
    closed = asyncio.Event()

    async def pump_container_to_ws() -> None:
        try:
            while not closed.is_set():
                try:
                    data = await loop.sock_recv(raw, 65536)
                except (BlockingIOError, InterruptedError):
                    await asyncio.sleep(0.01)
                    continue
                if not data:
                    break
                await ws.send_bytes(data)
        except Exception:
            pass
        finally:
            closed.set()

    async def pump_ws_to_container() -> None:
        try:
            while not closed.is_set():
                message = await ws.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if "bytes" in message and message["bytes"]:
                    if not read_only:
                        await loop.sock_sendall(raw, message["bytes"])
                elif "text" in message and message["text"]:
                    text = message["text"]
                    if text.startswith("{"):
                        try:
                            control = json.loads(text)
                        except json.JSONDecodeError:
                            control = None
                        if control and control.get("type") == "resize":
                            try:
                                api.exec_resize(
                                    exec_id,
                                    height=int(control["rows"]),
                                    width=int(control["cols"]),
                                )
                            except Exception:
                                pass
                            continue
                    if not read_only:
                        await loop.sock_sendall(raw, text.encode())
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            closed.set()

    tasks = [
        asyncio.create_task(pump_container_to_ws()),
        asyncio.create_task(pump_ws_to_container()),
    ]
    await closed.wait()
    for task in tasks:
        task.cancel()
    try:
        raw.close()
    except Exception:
        pass
    try:
        await ws.close()
    except Exception:
        pass
