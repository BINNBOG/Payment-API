import pytest
from pydantic import ValidationError

from app.models.enums import PaymentMethod
from app.schemas import PaymentCreate
from app.services.payments import build_installment_schedule, calculate_payment_amounts


def test_amount_without_promo_code() -> None:
    result = calculate_payment_amounts(
        price=1_990_000,
        promo_code=None,
    )
    
    assert result.amount == 1_990_000
    assert result.discount == 0
    
    
@pytest.mark.parametrize(
    "promo_code",
    [
        "KVITTO10",
        "kvitto10",
        "Kvitto10",
    ],
)
def test_amount_with_promo_code(promo_code: str) -> None:
    result = calculate_payment_amounts(price=1_990_000, promo_code=promo_code)
    
    assert result.amount == 1_791_000
    assert result.discount == 199_000
    
    
@pytest.mark.parametrize(
    "months",
    [
        3,
        6,
        12,
    ],
)
def test_installment_schedule(months: int) -> None:
    amount = 1_791_001

    schedule = build_installment_schedule(
        amount=amount,
        months=months,
    )

    assert len(schedule) == months
    assert sum(schedule) == amount
    assert max(schedule) - min(schedule) <= 1
    assert schedule == sorted(schedule,reverse=True)
    
    
def test_installment_months_are_required() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(tariff_id=1, email="user@example.com", method=PaymentMethod.INSTALLMENT)
        
def test_installment_months_forbidden_for_card() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(tariff_id=1, email="user@example.com", method=PaymentMethod.CARD, installment_months=3)
        
def test_unknown_promo_code() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(tariff_id=1, email="user@example.com", method=PaymentMethod.CARD, promo_code="UNKNOWN")