from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from app.services.pikepdf_service import PikepdfService
from app.services.file_manager import FileManager

router = APIRouter()

class ImageInfo(BaseModel):
    page: int
    width: int
    height: int
    color_space: str
    bits_per_component: int
    estimated_dpi: Optional[float] = None
    is_low_res: bool = False

class FontInfo(BaseModel):
    name: str
    subtype: str
    embedded: bool
    subset: bool

class BoxInfo(BaseModel):
    media_box: list[float]
    trim_box: Optional[list[float]] = None
    bleed_box: Optional[list[float]] = None
    art_box: Optional[list[float]] = None

class PreflightReport(BaseModel):
    success: bool
    file_name: str
    page_count: int
    pdf_version: str
    
    # Dimensions
    page_boxes: list[BoxInfo]
    has_bleed: bool
    bleed_mm: Optional[float] = None
    
    # Images
    images: list[ImageInfo]
    low_res_images: int
    min_dpi: Optional[float] = None
    
    # Fonts
    fonts: list[FontInfo]
    unembedded_fonts: int
    
    # Colors
    color_spaces: list[str]
    has_rgb: bool
    has_cmyk: bool
    spot_colors: list[str]
    
    # Warnings
    warnings: list[str]
    errors: list[str]

@router.post("/check", response_model=PreflightReport)
async def full_preflight_check(
    min_dpi: float = 300,
    file: UploadFile = File(...)
):
    """
    Comprehensive preflight check for print production.
    
    Checks:
    - Image resolution (warns if below min_dpi)
    - Font embedding
    - Color spaces (RGB, CMYK, spot colors)
    - Page boxes (trim, bleed)
    - PDF version compatibility
    """
    file_manager = FileManager()
    pikepdf = PikepdfService()
    
    try:
        input_path = await file_manager.save_upload(file)
        
        report = await pikepdf.full_preflight(
            input_path=input_path,
            min_dpi=min_dpi
        )
        
        return PreflightReport(
            success=True,
            file_name=file.filename,
            **report
        )
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.post("/images")
async def check_images(
    min_dpi: float = 300,
    file: UploadFile = File(...)
):
    """Check image resolution in PDF."""
    file_manager = FileManager()
    pikepdf = PikepdfService()
    
    try:
        input_path = await file_manager.save_upload(file)
        images = await pikepdf.check_images(input_path, min_dpi)
        
        low_res = [img for img in images if img.get("is_low_res")]
        
        return {
            "total_images": len(images),
            "low_res_count": len(low_res),
            "images": images,
            "passed": len(low_res) == 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.post("/spot-colors")
async def list_spot_colors(file: UploadFile = File(...)):
    """Extract list of spot colors from PDF."""
    file_manager = FileManager()
    pikepdf = PikepdfService()
    
    try:
        input_path = await file_manager.save_upload(file)
        colors = await pikepdf.get_spot_colors(input_path)
        
        return {
            "spot_colors": colors,
            "count": len(colors)
        }
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

