import os
import tempfile

# CRITICAL: isolate the test database BEFORE any tremblecode_server import —
# the engine binds to TC_DATABASE_URL at import time. Without this, the suite
# drops every table in the developer's live tremblecode.db (this happened once;
# never again).
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="tc-test-"), "test.db")
os.environ["TC_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from tremblecode_server.config import get_settings  # noqa: E402
from tremblecode_server.database import Base, SessionLocal, engine, init_db  # noqa: E402
from tremblecode_server.main import app  # noqa: E402
from tremblecode_server.services.seed import seed_builtin_templates  # noqa: E402

# belt and suspenders: refuse to run against anything but the test file
assert "tc-test-" in str(engine.url), (
    f"tests are bound to {engine.url} — refusing to touch a non-test database"
)
assert "tc-test-" in get_settings().database_url


@pytest.fixture
async def client():
    # Fresh schema per test for isolation.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    async with SessionLocal() as session:
        await seed_builtin_templates(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
