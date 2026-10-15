from typing import Literal 
from uuid import UUID
from pydantic import BaseModel
from app.models import PaymentStatus


class BankWebhookRequest(BaseModel):
    payment_id: UUID
    status: PaymentStatus


class BankWebhookResponse(BaseModel):
    result: Literal["ok"] = "ok"


class InvalidTransitionResponse(BaseModel):
    error: Literal["invalid_transition"]