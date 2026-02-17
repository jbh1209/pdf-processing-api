from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.admin import router as admin_router
from app.api.imposition import router as imposition_router
from app.api.color import router as color_router
from app.api.preflight import router as preflight_router
from app.api.manipulate import router as manipulate_router
from app.api.page_boxes import router as page_boxes_router  # NEW

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(admin_router, tags=["Admin"])
api_router.include_router(imposition_router, prefix="/imposition", tags=["Imposition"])
api_router.include_router(color_router, prefix="/color", tags=["Color Management"])
api_router.include_router(preflight_router, prefix="/preflight", tags=["Preflight"])
api_router.include_router(manipulate_router, prefix="/manipulate", tags=["Manipulation"])
api_router.include_router(page_boxes_router, prefix="/page-boxes", tags=["Page Boxes"])  # NEW
