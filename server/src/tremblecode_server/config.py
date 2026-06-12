from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TC_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./tremblecode.db"
    redis_url: str = "redis://localhost:6379/0"

    host: str = "0.0.0.0"
    port: int = 8400
    # URL containers use to reach this server
    server_url_from_container: str = "http://host.docker.internal:8400"
    redis_url_from_container: str = "redis://host.docker.internal:6379/0"

    # Host directory where project dirs are created (identity-mounted into containers)
    projects_dir: Path = Path.home() / "tremblecode-projects"
    # Persistent Claude home shared by all sandboxes (login once)
    agent_home: Path = Path.home() / ".tremblecode" / "agent-home"

    sandbox_image: str = "tremblecode-sandbox:base"
    sandbox_image_flutter: str = "tremblecode-sandbox:flutter"
    port_block_start: int = 34000
    port_block_size: int = 10

    # Shared secret for /internal endpoints (containers receive it via env)
    internal_secret: str = "dev-internal-secret"
    # Fernet key for encrypting secrets at rest; generated if empty
    fernet_key: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    # Message reliability
    ack_timeout_seconds: int = 900
    ack_max_nudges: int = 2

    repo_root: Path = Path(__file__).resolve().parents[3]

    @property
    def templates_dir(self) -> Path:
        return self.repo_root / "templates"

    @property
    def runtime_dir(self) -> Path:
        return self.repo_root / "sandbox" / "runtime"


@lru_cache
def get_settings() -> Settings:
    return Settings()
