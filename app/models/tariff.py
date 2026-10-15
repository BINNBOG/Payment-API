from sqlalchemy import CheckConstraint, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TariffTitle


class Tariff(Base):
    __tablename__ = "tariffs"
    __table_args__ = (
        CheckConstraint(
            "price > 0",
            name="ck_tariffs_price_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[TariffTitle] = mapped_column(
        Enum(
            TariffTitle,
            name="tariff_title",
            native_enum=False,
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        unique=True,
        nullable=False,
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
