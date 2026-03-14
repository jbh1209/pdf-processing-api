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

async def rasterize_pages(
    self,
    input_path: Path,
    output_dir: Path,
    pages: list[int] | None = None,
    dpi: int = 150,
    fmt: str = "png",
    max_width: int | None = None,
) -> list[dict]:
    """Render PDF pages to PNG/JPEG images using Ghostscript."""
    import base64

    device = "png16m" if fmt == "png" else "jpeg"
    ext = fmt

    # Get page count if no specific pages requested
    if not pages:
        # Use pdfcpu or gs to get page count
        cmd_count = [
            self.gs_path, "-dNODISPLAY", "-dBATCH", "-dNOPAUSE",
            "-c", f"({input_path}) (r) file runpdfbegin pdfpagecount = quit"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd_count,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        total = int(stdout.decode().strip())
        pages = list(range(1, total + 1))

    results = []
    for page_num in pages:
        out_file = output_dir / f"page-{page_num:04d}.{ext}"

        cmd = [
            self.gs_path,
            "-dSAFER", "-dBATCH", "-dNOPAUSE",
            f"-sDEVICE={device}",
            f"-r{dpi}",
            f"-dFirstPage={page_num}",
            f"-dLastPage={page_num}",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-sOutputFile={out_file}",
            str(input_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise PDFProcessingError(
                f"Ghostscript rasterize failed on page {page_num}: {stderr.decode()}"
            )

        # Optional resize with Pillow if max_width set
        if max_width:
            from PIL import Image
            img = Image.open(out_file)
            if img.width > max_width:
                ratio = max_width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)
                img.save(out_file)

        # Read and encode
        from PIL import Image
        img = Image.open(out_file)
        w, h = img.size

        with open(out_file, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        results.append({
            "page": page_num,
            "image_base64": b64,
            "width": w,
            "height": h,
            "format": fmt,
        })

    return results
