from pydantic import BaseModel, ConfigDict

from app.models import TariffTitle


class TariffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: TariffTitle
    price: int
