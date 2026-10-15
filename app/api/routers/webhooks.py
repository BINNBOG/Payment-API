from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_webhook_signature
from app.db.session import get_db
from app.schemas import (
    BankWebhookRequest,
    BankWebhookResponse,
    InvalidTransitionResponse,
)
from app.services.payments import (
    InvalidPaymentTransitionError,
    PaymentNotFoundError,
    update_payment_status,
)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post(
    "/bank",
    response_model=BankWebhookResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_webhook_signature)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid webhook signature"},
        status.HTTP_404_NOT_FOUND: {"description": "Payment not found"},
        status.HTTP_409_CONFLICT: {
            "model": InvalidTransitionResponse,
            "description": "Invalid status transition",
        },
    },
)
async def process_bank_webhook(
    webhook_data: BankWebhookRequest, session: Annotated[AsyncSession, Depends(get_db)]
) -> BankWebhookResponse | Response:
    try:
        await update_payment_status(
            session=session,
            payment_id=webhook_data.payment_id,
            new_status=webhook_data.status,
        )
    except PaymentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="payment not found",
        ) from error
    except InvalidPaymentTransitionError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "invalid_transition"},
        )

    return BankWebhookResponse()
