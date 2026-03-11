"""Pytest fixtures for vLLM Manager backend tests."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import hash_password, generate_api_token
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.models.access_token import AccessToken

# ── In-memory SQLite for tests ────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

AsyncTestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session that is rolled back after each test."""
    async with engine.connect() as conn:
        await conn.begin_nested()
        session = AsyncTestSession(bind=conn)
        yield session
        await session.rollback()
        await session.close()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Fake Redis client using DB 15 (test database)."""
    client = Redis.from_url("redis://127.0.0.1:6379/15", decode_responses=False)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("AdminPass1!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        username="user1",
        email="user1@example.com",
        hashed_password=hash_password("UserPass1!"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    from app.core.security import create_access_token
    return create_access_token({"sub": str(admin_user.id), "role": admin_user.role})


@pytest_asyncio.fixture
async def api_token(db_session: AsyncSession, regular_user: User) -> tuple[str, AccessToken]:
    raw, hashed = generate_api_token()
    token = AccessToken(
        user_id=regular_user.id,
        name="test-token",
        hashed_token=hashed,
        scoped_instance_ids=[],
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return raw, token


@pytest.fixture
def mock_docker():
    with patch("app.services.vllm_service.docker") as mock:
        client = MagicMock()
        mock.from_env.return_value = client
        client.containers.run.return_value = MagicMock(id="fake-container-id", status="running")
        yield client


@pytest.fixture
def mock_hf():
    with patch("app.services.hf_service.snapshot_download", new_callable=AsyncMock) as mock:
        mock.return_value = "/fake/hf/cache/models--org--model"
        yield mock


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncGenerator[AsyncClient, None]:
    from app.dependencies import get_db, get_redis

    async def override_db():
        yield db_session

    async def override_redis():
        yield redis_client

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
