from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Tariff, TariffTitle

INITIAL_TARIFFS = {
    TariffTitle.BASIC: 990_000,
    TariffTitle.STANDARD: 1_990_000,
    TariffTitle.PREMIUM: 2_990_000,
}


async def seed_tariffs(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session, session.begin():
        result = await session.scalars(select(Tariff.title))
        existing_titles = set(result.all())
        tariffs_to_create = [
            Tariff(title=title, price=price)
            for title, price in INITIAL_TARIFFS.items()
            if title not in existing_titles
        ]
        session.add_all(tariffs_to_create)
