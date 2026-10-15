from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.services.tariffs import seed_tariffs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    engine = create_db_engine(db_url=settings.db_url, echo=settings.db_echo)
    session_factory = create_session_factory(engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    try:
        await seed_tariffs(session_factory)
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Kvitto Payments API", lifespan=lifespan)
    app.include_router(api_router)

    @app.get("/")
    async def home_page() -> dict[str, str]:
        return {"message": "Home page for Kvitto."}

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
