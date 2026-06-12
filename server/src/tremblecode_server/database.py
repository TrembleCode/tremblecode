from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# additive column migrations: create_all never ALTERs existing tables, and
# there is no alembic in v2 — each entry is (table, column, ddl, backfill)
_COLUMN_MIGRATIONS = [
    (
        "agent_templates",
        "effort",
        "ALTER TABLE agent_templates ADD COLUMN effort VARCHAR(16) DEFAULT 'medium'",
        "UPDATE agent_templates SET effort='high' WHERE kind='lead'",
    ),
    (
        "project_agents",
        "effort",
        "ALTER TABLE project_agents ADD COLUMN effort VARCHAR(16) DEFAULT 'medium'",
        # leads still planning get high; executing projects stay medium
        "UPDATE project_agents SET effort='high' WHERE kind='lead' AND project_id IN "
        "(SELECT id FROM projects WHERE status IN "
        "('DISCUSSION','DRAFT','PLANNING','PLAN_REVIEW'))",
    ),
    (
        "projects",
        "archived",
        "ALTER TABLE projects ADD COLUMN archived BOOLEAN DEFAULT 0 NOT NULL",
        "",
    ),
]


async def _ensure_columns(conn) -> None:
    for table, column, ddl, backfill in _COLUMN_MIGRATIONS:
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        if column in {row[1] for row in rows}:
            continue
        await conn.execute(text(ddl))
        if backfill:
            await conn.execute(text(backfill))


async def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
