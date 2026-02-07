from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid

from app.services.ghostscript import GhostscriptService
from app.services.file_manager import FileManager
from app.config import settings

router = APIRouter()

class ColorConversionResponse(BaseModel):
    success: bool
    message: str
    output_file_id: str
    profile_used: str
    original_colorspace: Optional[str] = None

@router.get("/profiles")
async def list_profiles():
    """List available ICC profiles for color conversion."""
    profiles = []
    if settings.icc_profiles_dir.exists():
        for f in settings.icc_profiles_dir.glob("*.icc"):
            profiles.append({
                "name": f.stem,
                "filename": f.name,
                "path": str(f)
            })
    
    return {
        "profiles": profiles,
        "default": settings.default_cmyk_profile
    }

@router.post("/rgb-to-cmyk", response_model=ColorConversionResponse)
async def convert_rgb_to_cmyk(
    profile: str = Query(default=None, description="ICC profile name (without .icc)"),
    file: UploadFile = File(...)
):
    """
    Convert RGB PDF to CMYK using specified ICC profile.
    
    Default profile: ISOcoated_v2_eci (FOGRA39 - European standard)
    """
    file_manager = FileManager()
    gs = GhostscriptService()
    
    profile_name = profile or settings.default_cmyk_profile.replace(".icc", "")
    profile_path = settings.icc_profiles_dir / f"{profile_name}.icc"
    
    if not profile_path.exists():
        raise HTTPException(
            status_code=400, 
            detail=f"ICC profile '{profile_name}' not found. Use /color/profiles to list available profiles."
        )
    
    try:
        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")
        
        result = await gs.convert_to_cmyk(
            input_path=input_path,
            output_path=output_path,
            icc_profile=profile_path
        )
        
        return ColorConversionResponse(
            success=True,
            message="Successfully converted to CMYK",
            output_file_id=output_id,
            profile_used=profile_name,
            original_colorspace=result.get("original_colorspace")
        )
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.post("/flatten", response_model=ColorConversionResponse)
async def flatten_transparency(
    file: UploadFile = File(...)
):
    """
    Flatten transparency in PDF for print production.
    
    Converts all transparent objects to opaque for reliable printing.
    """
    file_manager = FileManager()
    gs = GhostscriptService()
    
    try:
        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")
        
        await gs.flatten_transparency(
            input_path=input_path,
            output_path=output_path
        )
        
        return ColorConversionResponse(
            success=True,
            message="Successfully flattened transparency",
            output_file_id=output_id,
            profile_used="N/A"
        )
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.get("/download/{file_id}")
async def download_converted(file_id: str):
    """Download color-converted PDF."""
    file_manager = FileManager()
    file_path = file_manager.get_temp_path(f"{file_id}.pdf")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"cmyk_{file_id}.pdf"
    )

