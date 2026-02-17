from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    # API Configuration
    api_key: Optional[str] = None
    api_title: str = "PDF Processing API"
    api_version: str = "1.0.0"
    
    # File handling
    max_file_size_mb: int = 100
    temp_dir: Path = Path("/app/temp")
    temp_file_ttl_seconds: int = 3600
    
    # Tool paths
    ghostscript_path: str = "gs"
    pdfcpu_path: str = "pdfcpu"
    icc_profiles_dir: Path = Path("/app/icc_profiles")
    
    # Default ICC profile for CMYK conversion
    default_cmyk_profile: str = "ISOcoated_v2_eci.icc"

    # Admin/ops
    admin_key: Optional[str] = None  # Protects /admin endpoints (query ?key= or X-Admin-Key header)

    # Capacity / overload protection (especially for CPU+RAM heavy endpoints like /imposition/labels)
    max_concurrent_jobs: int = 1
    max_job_queue: int = 10
    job_acquire_timeout_seconds: int = 0  # 0 = don't wait; return 503 when busy (set >0 to wait briefly)
    job_timeout_seconds: int = 300  # Soft timeout for heavy processing sections

    # Memory watchdog (optional). If >0, process exits when RSS exceeds this value (MB) so platform can restart it.
    max_rss_mb: int = 0

    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()

