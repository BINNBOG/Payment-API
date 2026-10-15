from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.constants import ALLOWED_INSTALLMENT_MONTHS, PROMO_CODE, PROMO_DISCOUNT_PERCENT
from app.models import PaymentStatus, PaymentMethod, Payment, Tariff
from app.schemas import PaymentCreate


ALLOWED_STATUS_TRANSITIONS = {
    PaymentStatus.PENDING: frozenset({PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}),
    PaymentStatus.SUCCEEDED: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
}

@dataclass(frozen=True, slots=True)
class PaymentAmounts:
    amount: int
    discount: int
    
@dataclass(frozen=True, slots=True)
class PaymentCreationResult:
    payment: Payment
    created: bool
    
    
class TariffNotFoundError(Exception):
    def __init__(self, tariff_id: int) -> None:
        self.tariff_id = tariff_id
        super().__init__(f"tariff with id={tariff_id} not found")
        
        
class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: UUID) -> None:
        self.payment_id = payment_id
        super().__init__(f"payment with id={payment_id} not found")
    
    
class InvalidPaymentTransitionError(Exception):
    def __init__(self, current_status: PaymentStatus, new_status: PaymentStatus) -> None:
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(f"transition from {current_status} to {new_status} is not allowed")
        
    
def calculate_payment_amounts(price: int, promo_code: str | None) -> PaymentAmounts:
    if price <= 0:
        raise ValueError("price must be positive")
    
    discount = 0
    if promo_code is not None:
        normalized_code = promo_code.strip().upper()
        
        if normalized_code != PROMO_CODE:
            raise ValueError("unknown promo code")
        
        discount = price * PROMO_DISCOUNT_PERCENT // 100
        
    return PaymentAmounts(amount=price - discount, discount=discount)


def build_installment_schedule(amount: int, months: int) -> list[int]:
    if amount <= 0:
        raise ValueError("amount must be positive")
    
    if months not in ALLOWED_INSTALLMENT_MONTHS:
        raise ValueError("months must be 3, 6 or 12")
    
    base_payment, remainder = divmod(amount, months)
    return [base_payment + (1 if payment_number < remainder else 0) for payment_number in range(months)]


async def get_payment_by_key(session: AsyncSession, idempotency_key: str) -> Payment | None:
    statement = select(Payment).where(Payment.idempotency_key == idempotency_key)
    return await session.scalar(statement)

async def create_payment(session: AsyncSession, payment_data: PaymentCreate, idempotency_key: str | None) -> PaymentCreationResult:
    if idempotency_key is not None:
        existing_payment = await get_payment_by_key(session, idempotency_key)
        
        if existing_payment is not None:
            return PaymentCreationResult(payment=existing_payment, created=False)
    
    tariff = await session.get(Tariff, payment_data.tariff_id)
    if tariff is None:
        raise TariffNotFoundError(tariff_id=payment_data.tariff_id)
    
    amounts = calculate_payment_amounts(tariff.price, payment_data.promo_code)
    
    schedule = None
    if payment_data.method == PaymentMethod.INSTALLMENT:
        if payment_data.installment_months is None:
            raise ValueError("installment_months is required")
        
        schedule = build_installment_schedule(amounts.amount, payment_data.installment_months)
    
    payment = Payment(
        status=PaymentStatus.PENDING,
        tariff_id=tariff.id,
        amount=amounts.amount,
        discount=amounts.discount,
        method=payment_data.method,
        installment_months=payment_data.installment_months,
        schedule=schedule,
        email=str(payment_data.email),
        idempotency_key=idempotency_key,
    )
    
    session.add(payment)
    
    try:
        await session.commit()
    except IntegrityError: # safe from dublicats
        await session.rollback()

        if idempotency_key is None:
            raise

        existing_payment = await get_payment_by_key(session, idempotency_key)

        if existing_payment is None:
            raise

        return PaymentCreationResult(payment=existing_payment, created=False)

    await session.refresh(payment)

    return PaymentCreationResult(payment=payment, created=True)
    
    
async def get_payment_by_id(session: AsyncSession, payment_id: UUID) -> Payment | None:
    return await session.get(Payment, payment_id)


def is_status_transition_allowed(current_status: PaymentStatus, new_status: PaymentStatus) -> bool:
    allowed_statuses = ALLOWED_STATUS_TRANSITIONS[current_status]
    return new_status in allowed_statuses


async def update_payment_status(session: AsyncSession, payment_id: UUID, new_status: PaymentStatus) -> Payment:
    async with session.begin():
        statement = select(Payment).where(Payment.id == payment_id).with_for_update()
        payment = await session.scalar(statement)

        if payment is None:
            raise PaymentNotFoundError(payment_id)

        if not is_status_transition_allowed(payment.status, new_status):
            raise InvalidPaymentTransitionError(payment.status, new_status)
        
        payment.status = new_status
        
    return payment