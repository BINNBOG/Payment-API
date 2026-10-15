from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.constants import PROMO_CODE
from app.models import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    tariff_id: int = Field(gt=0)
    email: EmailStr
    method: PaymentMethod
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @field_validator("promo_code")
    @classmethod
    def validate_promo_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_code = value.strip().upper()
        if normalized_code != PROMO_CODE:
            raise ValueError("unknown promo code")

        return normalized_code

    @model_validator(mode="after")
    def validate_installment(self):
        if self.method == PaymentMethod.INSTALLMENT and self.installment_months is None:
            raise ValueError("installment_months is required for installment method")

        if self.method != PaymentMethod.INSTALLMENT and self.installment_months is not None:
            raise ValueError("installment_months is allowed only for installment method")

        return self


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: PaymentStatus
    tariff_id: int
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: EmailStr
    created_at: datetime
