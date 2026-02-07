import subprocess
import asyncio
from pathlib import Path
import logging

from app.config import settings
from app.utils.exceptions import PDFProcessingError

logger = logging.getLogger(__name__)

class GhostscriptService:
    def __init__(self):
        self.gs_path = settings.ghostscript_path
    
    async def convert_to_cmyk(
        self, 
        input_path: Path, 
        output_path: Path,
        icc_profile: Path
    ) -> dict:
        """Convert PDF to CMYK using specified ICC profile."""
        
        cmd = [
            self.gs_path,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dNOCACHE",
            "-sDEVICE=pdfwrite",
            "-sColorConversionStrategy=CMYK",
            "-sProcessColorModel=DeviceCMYK",
            f"-sOutputICCProfile={icc_profile}",
            "-dOverrideICC=true",
            "-sColorConversionStrategyForImages=CMYK",
            f"-sOutputFile={output_path}",
            str(input_path)
        ]
        
        logger.info(f"Running Ghostscript CMYK conversion: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise PDFProcessingError(f"Ghostscript CMYK conversion failed: {error_msg}")
            
            return {"success": True, "original_colorspace": "RGB"}
            
        except Exception as e:
            logger.error(f"Ghostscript error: {e}")
            raise PDFProcessingError(str(e))
    
    async def flatten_transparency(
        self,
        input_path: Path,
        output_path: Path
    ) -> dict:
        """Flatten transparency in PDF."""
        
        cmd = [
            self.gs_path,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dNOCACHE",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",  # Forces transparency flattening
            "-dHaveTransparency=false",
            f"-sOutputFile={output_path}",
            str(input_path)
        ]
        
        logger.info(f"Running Ghostscript transparency flatten")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise PDFProcessingError(f"Ghostscript flatten failed: {error_msg}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Ghostscript error: {e}")
            raise PDFProcessingError(str(e))

