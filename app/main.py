from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from app.config import settings
from app.api.routes import api_router
from app.utils.exceptions import PDFProcessingError
from app.utils.capacity import CapacityManager
from app.utils.runtime import get_rss_mb

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Professional PDF processing API for print production",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key middleware (optional)
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if settings.api_key:
        # Skip auth for health checks and docs
        if request.url.path in ["/health", "/health/detailed", "/docs", "/redoc", "/openapi.json", "/admin", "/admin/status"]:
            return await call_next(request)
        
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"}
            )
    
    return await call_next(request)

# Request timing middleware
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    return response

# Exception handlers
@app.exception_handler(PDFProcessingError)
async def pdf_processing_exception_handler(request: Request, exc: PDFProcessingError):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_type": "pdf_processing_error"}
    )

# Include API routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    # Ensure temp directory exists
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Temp directory: {settings.temp_dir}")

    # Capacity manager (backpressure for heavy endpoints)
    app.state.capacity_manager = CapacityManager(
        max_concurrent=settings.max_concurrent_jobs,
        max_queue=settings.max_job_queue,
    )
    logger.info(
        f"Capacity: max_concurrent_jobs={settings.max_concurrent_jobs}, "
        f"max_job_queue={settings.max_job_queue}, "
        f"acquire_timeout_s={settings.job_acquire_timeout_seconds}"
    )

    # Optional memory watchdog (exits process when RSS exceeds threshold so the platform restarts it)
    if settings.max_rss_mb and settings.max_rss_mb > 0:
        import asyncio, os
        async def _watchdog():
            while True:
                rss = get_rss_mb()
                if rss and rss > float(settings.max_rss_mb):
                    logger.error(f"Memory watchdog triggered: RSS={rss:.0f}MB > {settings.max_rss_mb}MB. Exiting for restart.")
                    os._exit(1)
                await asyncio.sleep(5)
        app.state._watchdog_task = asyncio.create_task(_watchdog())
        logger.info(f"Memory watchdog enabled: max_rss_mb={settings.max_rss_mb}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down PDF Processing API")

