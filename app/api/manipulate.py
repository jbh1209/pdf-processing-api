"""
PDF Manipulation API - Rotate and Split operations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import base64
import logging
from io import BytesIO

from app.services.file_manager import FileManager
import pikepdf

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Rotate ──────────────────────────────────────────────

class RotateRequest(BaseModel):
    pdf_url: str
    angle: int = 90


class RotateResponse(BaseModel):
    rotated_pdf_base64: str
    angle: int
    page_count: int


@router.post("/rotate", response_model=RotateResponse)
async def rotate_pdf(request: RotateRequest):
    """Rotate all pages in a PDF by a given angle (90, 180, or 270)."""
    if request.angle not in (90, 180, 270):
        raise HTTPException(400, "angle must be 90, 180, or 270")

    file_manager = FileManager()
    input_path = None

    try:
        input_path = await file_manager.download_from_url(request.pdf_url)
        pdf = pikepdf.Pdf.open(input_path)

        for page in pdf.pages:
            page.rotate(request.angle, relative=True)

        output = BytesIO()
        pdf.save(output)
        pdf_bytes = output.getvalue()

        return RotateResponse(
            rotated_pdf_base64=base64.b64encode(pdf_bytes).decode(),
            angle=request.angle,
            page_count=len(pdf.pages),
        )
    except Exception as e:
        logger.error(f"Rotate error: {e}")
        raise HTTPException(422, str(e))
    finally:
        if input_path:
            await file_manager.cleanup(input_path)


# ── Split ───────────────────────────────────────────────

class SplitRequest(BaseModel):
    pdf_url: str


class SplitPage(BaseModel):
    page_number: int
    pdf_base64: str
    width_pts: float
    height_pts: float


class SplitResponse(BaseModel):
    page_count: int
    pages: List[SplitPage]


@router.post("/split", response_model=SplitResponse)
async def split_pdf(request: SplitRequest):
    """Split a multi-page PDF into individual single-page PDFs."""
    file_manager = FileManager()
    input_path = None

    try:
        input_path = await file_manager.download_from_url(request.pdf_url)
        source = pikepdf.Pdf.open(input_path)
        pages = []

        for i, page in enumerate(source.pages):
            single = pikepdf.Pdf.new()
            single.pages.append(page)

            mbox = page.get("/MediaBox")
            width_pts = float(mbox[2]) - float(mbox[0])
            height_pts = float(mbox[3]) - float(mbox[1])

            buf = BytesIO()
            single.save(buf)

            pages.append(SplitPage(
                page_number=i + 1,
                pdf_base64=base64.b64encode(buf.getvalue()).decode(),
                width_pts=width_pts,
                height_pts=height_pts,
            ))

        return SplitResponse(
            page_count=len(source.pages),
            pages=pages,
        )
    except Exception as e:
        logger.error(f"Split error: {e}")
        raise HTTPException(422, str(e))
    finally:
        if input_path:
            await file_manager.cleanup(input_path)


# ── Ping (keep existing) ───────────────────────────────

@router.get("/ping")
async def ping():
    return {"ok": True}
