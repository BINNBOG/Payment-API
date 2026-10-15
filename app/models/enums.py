from enum import StrEnum


class TariffTitle(StrEnum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


class PaymentMethod(StrEnum):
    CARD = "card"
    SBP = "sbp"
    INSTALLMENT = "installment"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
