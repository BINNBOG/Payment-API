from collections.abc import AsyncIterator
from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(db_url: str, echo: bool=False) -> AsyncEngine:
    return create_async_engine(
        db_url,
        echo=echo,
        pool_pre_ping=True,
    )
    
def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False)

async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session
    