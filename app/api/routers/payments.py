from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.schemas import PaymentCreate, PaymentResponse
from app.services.payments import TariffNotFoundError, create_payment, get_payment_by_id


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": PaymentResponse,
            "description": "Payment with this idempotency key already exists",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Tariff not found",
        },
    },
)
async def create_payment_endpoint(
    payment_data: PaymentCreate,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", min_length=1, max_length=255)] = None,
) -> PaymentResponse:
    try: 
        result = await create_payment(session, payment_data, idempotency_key)
    except TariffNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="tariff not found",
        ) from error
        
    if not result.created:
        response.status_code = status.HTTP_200_OK
        
    return PaymentResponse.model_validate(result.payment)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Payment not found"}},
)
async def get_payment_endpoint(payment_id: UUID, session: Annotated[AsyncSession, Depends(get_db)]) -> PaymentResponse:
    payment = await get_payment_by_id(session, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payment not found",
        )
    return PaymentResponse.model_validate(payment)