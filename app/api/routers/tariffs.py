from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Tariff
from app.schemas import TariffResponse


router = APIRouter(
    prefix="/tariffs",
    tags=["tariffs"],
)


@router.get("", response_model=list[TariffResponse], status_code=200)
async def get_tariffs(session: Annotated[AsyncSession, Depends(get_db)]) -> list[Tariff]:
    statement = select(Tariff).order_by(Tariff.price)
    result = await session.scalars(statement)
    return list(result.all())