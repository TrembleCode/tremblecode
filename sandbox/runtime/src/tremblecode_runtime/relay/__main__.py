import uvicorn

from ..config import get_config
from .app import app


def main() -> None:
    cfg = get_config()
    uvicorn.run(app, host=cfg.relay_host, port=cfg.relay_port, log_level="info")


if __name__ == "__main__":
    main()
