from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
import base64
import io
import math
import time
import gc
import httpx

from pypdf import PdfReader, PdfWriter, Transformation, PageObject

from app.services.pdfcpu import PdfcpuService
from app.services.file_manager import FileManager

router = APIRouter()


# =============================================================================
# EXISTING MODELS
# =============================================================================

class NupRequest(BaseModel):
    columns: int = Field(ge=1, le=20, description="Number of columns")
    rows: int = Field(ge=1, le=20, description="Number of rows")
    page_width_mm: Optional[float] = Field(default=320, description="Output page width in mm")
    page_height_mm: Optional[float] = Field(default=450, description="Output page height in mm")
    horizontal_gap_mm: Optional[float] = Field(default=0, description="Horizontal gap between items")
    vertical_gap_mm: Optional[float] = Field(default=0, description="Vertical gap between items")
    border: Optional[bool] = Field(default=False, description="Add border around each item")

class StepRepeatRequest(BaseModel):
    copies: int = Field(ge=1, description="Total copies needed")
    label_width_mm: float = Field(description="Individual label width")
    label_height_mm: float = Field(description="Individual label height")
    sheet_width_mm: float = Field(default=320, description="Output sheet width")
    sheet_height_mm: float = Field(default=450, description="Output sheet height")
    horizontal_gap_mm: float = Field(default=3, description="Gap between labels horizontally")
    vertical_gap_mm: float = Field(default=3, description="Gap between labels vertically")

class ImpositionResponse(BaseModel):
    success: bool
    message: str
    output_file_id: str
    pages_created: int
    items_per_page: int


# =============================================================================
# LABEL IMPOSITION MODELS (for Supabase edge function)
# =============================================================================

MM_TO_PT = 72.0 / 25.4  # 1 mm = 2.8346 points


class LabelDieline(BaseModel):
    roll_width_mm: float
    label_width_mm: float
    label_height_mm: float
    columns_across: int
    rows_around: int
    horizontal_gap_mm: float = 0
    vertical_gap_mm: float = 0
    corner_radius_mm: Optional[float] = None


class LabelSlot(BaseModel):
    slot: int
    item_id: str
    quantity_in_slot: int = 1
    pdf_url: str = ""
    needs_rotation: Optional[bool] = False
    rotation: Optional[int] = 0


class UploadConfig(BaseModel):
    """Signed upload URLs from Supabase storage — VPS uploads directly."""
    production_upload_url: str
    production_public_url: str
    proof_upload_url: Optional[str] = None
    proof_public_url: Optional[str] = None


class CallbackConfig(BaseModel):
    """Supabase credentials so VPS can update label_runs directly after processing."""
    supabase_url: str
    supabase_service_key: str
    run_id: str
    production_public_url: str
    proof_public_url: Optional[str] = None


class LabelImposeRequest(BaseModel):
    dieline: LabelDieline
    slots: List[LabelSlot]
    meters: float = 1.0
    include_dielines: bool = False
    upload_config: Optional[UploadConfig] = None
    callback_config: Optional[CallbackConfig] = None
    # Legacy — kept for backward compat but ignored when upload_config is set
    return_base64: bool = False


class LabelImposeResponse(BaseModel):
    success: bool
    # Legacy base64 fields (only populated when upload_config is NOT provided)
    production_pdf_base64: Optional[str] = None
    proof_pdf_base64: Optional[str] = None
    # Always returned
    frame_count: int
    total_meters: float


# =============================================================================
# EXISTING ENDPOINTS
# =============================================================================

@router.post("/nup", response_model=ImpositionResponse)
async def create_nup(
    columns: int = 3,
    rows: int = 8,
    file: UploadFile = File(...)
):
    """
    Create N-up imposition with specified grid layout.
    For labels: typically 4-6 columns, 8-12 rows depending on label size.
    """
    file_manager = FileManager()
    pdfcpu = PdfcpuService()

    try:
        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")

        grid = columns * rows

        result = await pdfcpu.nup(
            input_path=input_path,
            output_path=output_pa
