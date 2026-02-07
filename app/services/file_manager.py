import aiofiles
from pathlib import Path
import uuid
import asyncio
from fastapi import UploadFile
import logging

from app.config import settings

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self):
        self.temp_dir = settings.temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_upload(self, file: UploadFile) -> Path:
        """Save uploaded file to temp directory."""
        file_id = str(uuid.uuid4())
        extension = Path(file.filename).suffix if file.filename else ".pdf"
        file_path = self.temp_dir / f"{file_id}{extension}"
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        
        logger.info(f"Saved upload to {file_path}")
        return file_path
    
    def get_temp_path(self, filename: str) -> Path:
        """Get path for temp file."""
        return self.temp_dir / filename
    
    async def cleanup(self, file_path: Path):
        """Remove temp file."""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")
    
    async def cleanup_expired(self):
        """Remove files older than TTL."""
        import time
        ttl = settings.temp_file_ttl_seconds
        now = time.time()
        
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                age = now - file_path.stat().st_mtime
                if age > ttl:
                    await self.cleanup(file_path)

