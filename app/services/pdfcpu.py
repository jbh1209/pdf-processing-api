import subprocess
import asyncio
from pathlib import Path
import logging

from app.config import settings
from app.utils.exceptions import PDFProcessingError

logger = logging.getLogger(__name__)

class PdfcpuService:
    def __init__(self):
        self.pdfcpu_path = settings.pdfcpu_path
    
    async def nup(
        self,
        input_path: Path,
        output_path: Path,
        grid: int,
        page_size: str = None
    ) -> dict:
        """
        Create N-up imposition.
        
        Args:
            grid: Number of pages per sheet (e.g., 4, 9, 16, 24)
            page_size: Optional output page size (e.g., "320x450mm")
        """
        
        cmd = [self.pdfcpu_path, "nup", "-pages", "1"]
        
        if page_size:
            cmd.extend(["-psize", page_size])
        
        cmd.extend([str(output_path), str(grid), str(input_path)])
        
        logger.info(f"Running pdfcpu nup: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                raise PDFProcessingError(f"pdfcpu nup failed: {error_msg}")
            
            # Get page count from output
            pages = await self._get_page_count(output_path)
            
            return {"success": True, "pages": pages}
            
        except PDFProcessingError:
            raise
        except Exception as e:
            logger.error(f"pdfcpu error: {e}")
            raise PDFProcessingError(str(e))
    
    async def booklet(
        self,
        input_path: Path,
        output_path: Path
    ) -> dict:
        """Create booklet imposition."""
        
        cmd = [
            self.pdfcpu_path, "booklet",
            str(output_path), str(input_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                raise PDFProcessingError(f"pdfcpu booklet failed: {error_msg}")
            
            return {"success": True}
            
        except PDFProcessingError:
            raise
        except Exception as e:
            raise PDFProcessingError(str(e))
    
    async def _get_page_count(self, pdf_path: Path) -> int:
        """Get page count of PDF."""
        cmd = [self.pdfcpu_path, "info", str(pdf_path)]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # Parse page count from output
        output = stdout.decode()
        for line in output.split('\n'):
            if 'Page count' in line:
                return int(line.split(':')[1].strip())
        
        return 1

