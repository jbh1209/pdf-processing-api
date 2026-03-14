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

@api_router.post("/rasterize")
async def rasterize_pdf(request: Request):
    """Rasterize PDF pages to PNG/JPEG images."""
    body = await request.json()
    pdf_url = body.get("pdf_url")
    pages = body.get("pages")          # optional list of ints
    dpi = body.get("dpi", 150)         # default 150
    fmt = body.get("format", "png")    # png or jpeg
    max_width = body.get("max_width")  # optional pixel cap

    if not pdf_url:
        raise HTTPException(400, "pdf_url is required")
    if fmt not in ("png", "jpeg"):
        raise HTTPException(400, "format must be 'png' or 'jpeg'")
    if dpi < 36 or dpi > 600:
        raise HTTPException(400, "dpi must be between 36 and 600")

    capacity: CapacityManager = request.app.state.capacity_manager
    async with capacity.acquire(timeout=settings.job_acquire_timeout_seconds):
        with tempfile.TemporaryDirectory(dir=settings.temp_dir) as tmp:
            tmp_path = Path(tmp)
            input_pdf = tmp_path / "input.pdf"

            # Download the PDF
            await download_file(pdf_url, input_pdf)

            # Rasterize
            gs = GhostscriptService()
            results = await gs.rasterize_pages(
                input_path=input_pdf,
                output_dir=tmp_path,
                pages=pages,
                dpi=dpi,
                fmt=fmt,
                max_width=max_width,
            )

    return {"pages": results}
