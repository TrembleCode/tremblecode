import os
from dataclasses import dataclass, field


@dataclass
class RuntimeConfig:
    project_id: str = field(default_factory=lambda: os.environ["TC_PROJECT_ID"])
    project_slug: str = field(default_factory=lambda: os.environ.get("TC_PROJECT_SLUG", ""))
    project_dir: str = field(default_factory=lambda: os.environ["TC_PROJECT_DIR"])
    server_url: str = field(
        default_factory=lambda: os.environ.get("TC_SERVER", "http://host.docker.internal:8400")
    )
    redis_url: str = field(
        default_factory=lambda: os.environ.get(
            "TC_REDIS", "redis://host.docker.internal:6379/0"
        )
    )
    internal_secret: str = field(
        default_factory=lambda: os.environ.get("TC_INTERNAL_SECRET", "")
    )
    relay_host: str = "127.0.0.1"
    relay_port: int = 8765

    @property
    def stream_key(self) -> str:
        return f"tc:msg:{self.project_id}"

    @property
    def server_headers(self) -> dict:
        return {"X-Tremblecode-Secret": self.internal_secret}


_config: RuntimeConfig | None = None


def get_config() -> RuntimeConfig:
    global _config
    if _config is None:
        _config = RuntimeConfig()
    return _config
