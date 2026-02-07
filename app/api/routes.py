from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.imposition import router as imposition_router
from app.api.color import router as color_router
from app.api.preflight import router as preflight_router
from app.api.manipulate import router as manipulate_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(imposition_router, prefix="/imposition", tags=["Imposition"])
api_router.include_router(color_router, prefix="/color", tags=["Color Management"])
api_router.include_router(preflight_router, prefix="/preflight", tags=["Preflight"])
api_router.include_router(manipulate_router, prefix="/manipulate", tags=["Manipulation"])

