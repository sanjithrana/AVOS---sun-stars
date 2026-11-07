"""
Shared fixtures for api tests.

Tests that need real infrastructure are skipped automatically when it
isn't reachable, so `pytest` stays green on a laptop without Docker and
exercises everything in CI / docker compose:

    TEST_DATABASE_URL   Postgres (default: the compose DB's solunex_test)
    REDIS_URL           Redis for event-bus tests
    TEMPORAL_HOST       Temporal for workflow tests
    LIVE_API_URL        running API for tests/integration (opt-in)
"""

import os
import sys
import asyncio

# On Windows, asyncio defaults to ProactorEventLoop, which psycopg's async
# driver can't use ("Psycopg cannot use the 'ProactorEventLoop' to run in
# async mode"). Switch to SelectorEventLoop before pytest-asyncio creates
# any event loop. Linux/macOS (CI, Docker, this repo's usual dev machines)
# are unaffected - this only matters for `pytest` run directly on a
# Windows host outside Docker.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://solunex:solunex@postgres:5432/solunex_test",
)

# Point the application's own engine at the test DB *before* importing
# anything from src, so services/activities under test never touch the
# dev database.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("DATABASE_NULLPOOL", "true")
os.environ.setdefault("ASSETS_STORAGE_PATH", "/tmp/avos-test-assets")

import socket  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import src.database.models  # noqa: E402,F401  (registers all tables)
from src.database.base import Base  # noqa: E402
from src.database.models.human_gate import HumanGate  # noqa: E402,F401


def _reachable(url: str, default_port: int) -> bool:
    parsed = urlparse(url if "://" in url else f"tcp://{url}")
    host, port = parsed.hostname or "localhost", parsed.port or default_port
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


DB_AVAILABLE = _reachable(TEST_DATABASE_URL.replace("+psycopg", ""), 5432)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_AVAILABLE = _reachable(REDIS_URL, 6379)
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_AVAILABLE = _reachable(TEMPORAL_HOST, 7233)

requires_db = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")
requires_redis = pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
requires_temporal = pytest.mark.skipif(
    not (TEMPORAL_AVAILABLE and DB_AVAILABLE), reason="Temporal/Postgres not reachable"
)


async def _ensure_test_database() -> None:
    """Create the test database on first use (an existing Postgres volume
    predates it, and CREATE DATABASE can't run inside a transaction)."""
    from sqlalchemy.engine import make_url

    url = make_url(TEST_DATABASE_URL)
    admin = create_async_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await admin.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    if not DB_AVAILABLE:
        pytest.skip("Postgres not reachable")

    await _ensure_test_database()
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(autouse=True)
def _schema_for_db_tests(request):
    """Any test marked requires_db gets a migrated-equivalent schema."""
    if DB_AVAILABLE and request.node.get_closest_marker("skipif") is not None:
        request.getfixturevalue("test_engine")


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def clean_db(test_engine):
    """Truncate all tables before a test that commits data."""
    async with test_engine.begin() as connection:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


class CapturingEventBus:
    """Drop-in for EventBus that records published events in memory."""

    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> bool:
        self.events.append(event)
        return True

    def types(self) -> list[str]:
        return [e.event_type.value for e in self.events]


@pytest.fixture
def captured_events(monkeypatch) -> CapturingEventBus:
    bus = CapturingEventBus()
    monkeypatch.setattr("src.core.events.outbox.get_event_bus", lambda: bus)
    return bus
