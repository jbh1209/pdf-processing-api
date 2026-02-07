from fastapi import APIRouter
from pydantic import BaseModel
import subprocess
import shutil

from app.config import settings

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str

class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    tools: dict
    icc_profiles: list[str]

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.api_version
    )

@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    tools = {}
    
    # Check Ghostscript
    try:
        result = subprocess.run(
            [settings.ghostscript_path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        tools["ghostscript"] = {
            "available": True,
            "version": result.stdout.strip()
        }
    except Exception as e:
        tools["ghostscript"] = {"available": False, "error": str(e)}
    
    # Check pdfcpu
    try:
        result = subprocess.run(
            [settings.pdfcpu_path, "version"],
            capture_output=True, text=True, timeout=5
        )
        tools["pdfcpu"] = {
            "available": True,
            "version": result.stdout.strip().split('\n')[0]
        }
    except Exception as e:
        tools["pdfcpu"] = {"available": False, "error": str(e)}
    
    # Check pikepdf
    try:
        import pikepdf
        tools["pikepdf"] = {
            "available": True,
            "version": pikepdf.__version__
        }
    except Exception as e:
        tools["pikepdf"] = {"available": False, "error": str(e)}
    
    # List ICC profiles
    profiles = []
    if settings.icc_profiles_dir.exists():
        profiles = [f.name for f in settings.icc_profiles_dir.glob("*.icc")]
    
    all_available = all(t.get("available", False) for t in tools.values())
    
    return DetailedHealthResponse(
        status="healthy" if all_available else "degraded",
        version=settings.api_version,
        tools=tools,
        icc_profiles=profiles
    )

