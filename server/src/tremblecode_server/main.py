import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    agent_templates,
    agents,
    discussions,
    escalations,
    internal,
    mcp,
    messages,
    plans,
    projects,
    settings as settings_api,
    wiki,
    ws,
)
from .config import get_settings
from .database import SessionLocal, init_db
from .services.lifecycle import reconcile_on_boot
from .services.seed import seed_builtin_templates
from .services.watchdog import watchdog_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_builtin_templates(session)
    async with SessionLocal() as session:
        try:
            await reconcile_on_boot(session)
        except Exception:  # docker may be unavailable in tests/CI
            import logging

            logging.getLogger(__name__).exception("boot reconcile failed")
    watchdog = asyncio.create_task(watchdog_loop())
    yield
    watchdog.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TrembleCode", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": "2.0.0"}

    app.include_router(agent_templates.router)
    app.include_router(projects.router)
    app.include_router(agents.router)
    app.include_router(plans.router)
    app.include_router(discussions.router)
    app.include_router(messages.router)
    app.include_router(escalations.router)
    app.include_router(mcp.router)
    app.include_router(wiki.router)
    app.include_router(settings_api.router)
    app.include_router(internal.router)
    app.include_router(ws.router)

    return app


app = create_app()
