from fastapi import APIRouter

from app.api.routers.payments import router as payments_router
from app.api.routers.tariffs import router as tariffs_router
from app.api.routers.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(tariffs_router)
api_router.include_router(payments_router)
api_router.include_router(webhooks_router)
