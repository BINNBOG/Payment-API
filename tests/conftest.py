from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.session import get_db
from app.main import app
from app.services.tariffs import seed_tariffs


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest_asyncio.fixture
async def db_connection(settings: Settings) -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(settings.db_url, pool_pre_ping=True)

    async with engine.connect() as connection:
        transaction = await connection.begin()

        try:
            yield connection
        finally:
            if transaction.is_active:
                await transaction.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_connection: AsyncConnection, settings: Settings) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(
        bind=db_connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    await seed_tariffs(session_factory)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.state.settings = settings
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
