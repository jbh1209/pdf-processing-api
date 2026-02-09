"""
Page Boxes API - Extract PDF page boxes (MediaBox, TrimBox, BleedBox, etc.)
Accepts a URL instead of file upload for integration with Supabase Edge Functions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.services.pikepdf_service import PikepdfService
from app.services.file_manager import FileManager
import pikepdf

router = APIRouter()
logger = logging.getLogger(__name__)


class PageBoxesRequest(BaseModel):
    pdf_url: str


class BoxDimensions(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float


class PageBoxesResponse(BaseModel):
    mediabox: Optional[BoxDimensions] = None
    cropbox: Optional[BoxDimensions] = None
    bleedbox: Optional[BoxDimensions] = None
    trimbox: Optional[BoxDimensions] = None
    artbox: Optional[BoxDimensions] = None
    page_count: int = 1


@router.post("", response_model=PageBoxesResponse)
async def get_page_boxes(request: PageBoxesRequest):
    """
    Extract PDF page boxes from a URL.
    
    Downloads the PDF and extracts all page box definitions from the first page.
    Returns dimensions in PDF points (1 pt = 1/72 inch = 0.3528 mm).
    
    Box types:
    - MediaBox: Total page size (always present)
    - CropBox: Visible area when displayed/printed
    - BleedBox: Area including bleed for printing
    - TrimBox: Final trimmed size (finished piece)
    - ArtBox: Meaningful content area
    """
    file_manager = FileManager()
    pikepdf_service = PikepdfService()
    input_path = None
    
    try:
        logger.info(f"Downloading PDF from: {request.pdf_url[:80]}...")
        input_path = await file_manager.download_from_url(request.pdf_url)
        
        # Extract page boxes
        boxes = await pikepdf_service.get_page_boxes_detailed(input_path)
        
        # Get page count
        pdf = pikepdf.Pdf.open(input_path)
        page_count = len(pdf.pages)
        
        return PageBoxesResponse(**boxes, page_count=page_count)
        
    except Exception as e:
        logger.error(f"Page boxes extraction error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        if input_path:
            await file_manager.cleanup(input_path)
