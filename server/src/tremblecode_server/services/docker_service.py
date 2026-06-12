import asyncio
import logging
from pathlib import Path

import docker
from docker.errors import APIError, ImageNotFound, NotFound

from ..config import get_settings

logger = logging.getLogger(__name__)

_client: docker.DockerClient | None = None


def client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def container_name(slug: str) -> str:
    return f"tc-{slug}"


class SandboxError(RuntimeError):
    pass


def _image_exists(image: str) -> bool:
    try:
        client().images.get(image)
        return True
    except ImageNotFound:
        return False


def _create_container(
    *,
    slug: str,
    image: str,
    host_dir: Path,
    project_id: str,
    port_base: int,
    api_key: str | None,
) -> str:
    settings = get_settings()
    name = container_name(slug)

    ports = {
        f"{p}/tcp": p for p in range(port_base, port_base + settings.port_block_size)
    }
    env = {
        "TC_PROJECT_ID": project_id,
        "TC_PROJECT_SLUG": slug,
        "TC_PROJECT_DIR": str(host_dir),
        "TC_SERVER": settings.server_url_from_container,
        "TC_REDIS": settings.redis_url_from_container,
        "TC_INTERNAL_SECRET": settings.internal_secret,
    }
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key

    settings.agent_home.mkdir(parents=True, exist_ok=True)
    volumes = {
        # identity mount: same absolute path inside the container so git
        # worktree pointers stay valid
        str(host_dir): {"bind": str(host_dir), "mode": "rw"},
        str(settings.agent_home): {"bind": "/home/agent", "mode": "rw"},
        str(settings.runtime_dir): {"bind": "/opt/tremblecode", "mode": "ro"},
    }

    container = client().containers.run(
        image,
        name=name,
        detach=True,
        environment=env,
        volumes=volumes,
        ports=ports,
        extra_hosts={"host.docker.internal": "host-gateway"},
        restart_policy={"Name": "unless-stopped"},
        hostname=name,
    )
    return container.id


async def create_sandbox(
    *,
    slug: str,
    image: str,
    host_dir: Path,
    project_id: str,
    port_base: int,
    api_key: str | None = None,
) -> str:
    if not _image_exists(image):
        raise SandboxError(
            f"sandbox image '{image}' not found — build it with `make image`"
        )
    # remove any stale container with the same name
    await remove_sandbox(slug)
    return await asyncio.to_thread(
        _create_container,
        slug=slug,
        image=image,
        host_dir=host_dir,
        project_id=project_id,
        port_base=port_base,
        api_key=api_key,
    )


def _container_status(slug: str) -> str | None:
    try:
        return client().containers.get(container_name(slug)).status
    except NotFound:
        return None


async def sandbox_status(slug: str) -> str | None:
    """Returns docker status (running|exited|...) or None if absent."""
    return await asyncio.to_thread(_container_status, slug)


async def start_sandbox(slug: str) -> None:
    def _start():
        client().containers.get(container_name(slug)).start()

    await asyncio.to_thread(_start)


async def stop_sandbox(slug: str) -> None:
    def _stop():
        try:
            client().containers.get(container_name(slug)).stop(timeout=10)
        except NotFound:
            pass

    await asyncio.to_thread(_stop)


async def remove_sandbox(slug: str) -> None:
    def _remove():
        try:
            client().containers.get(container_name(slug)).remove(force=True)
        except NotFound:
            pass
        except APIError as exc:
            logger.warning("failed to remove container %s: %s", slug, exc)

    await asyncio.to_thread(_remove)


async def exec_in_sandbox(
    slug: str, cmd: list[str], user: str = "agent", workdir: str | None = None
) -> tuple[int, str]:
    def _exec():
        container = client().containers.get(container_name(slug))
        result = container.exec_run(cmd, user=user, workdir=workdir)
        return result.exit_code, result.output.decode(errors="replace")

    return await asyncio.to_thread(_exec)
