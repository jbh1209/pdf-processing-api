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
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()

