from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from app.services.pdfcpu import PdfcpuService
from app.services.file_manager import FileManager

router = APIRouter()

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
        # Save uploaded file
        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")
        
        # Calculate grid
        grid = columns * rows
        
        # Run pdfcpu nup
        result = await pdfcpu.nup(
            input_path=input_path,
            output_path=output_path,
            grid=grid
        )
        
        return ImpositionResponse(
            success=True,
            message=f"Created {columns}x{rows} N-up imposition",
            output_file_id=output_id,
            pages_created=result["pages"],
            items_per_page=grid
        )
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.post("/step-repeat", response_model=ImpositionResponse)
async def create_step_repeat(
    request: StepRepeatRequest,
    file: UploadFile = File(...)
):
    """
    Create step-and-repeat imposition for labels.
    
    Automatically calculates optimal grid based on label and sheet dimensions.
    """
    file_manager = FileManager()
    pdfcpu = PdfcpuService()
    
    try:
        # Calculate how many labels fit
        columns = int((request.sheet_width_mm - request.horizontal_gap_mm) / 
                     (request.label_width_mm + request.horizontal_gap_mm))
        rows = int((request.sheet_height_mm - request.vertical_gap_mm) / 
                  (request.label_height_mm + request.vertical_gap_mm))
        
        labels_per_sheet = columns * rows
        sheets_needed = -(-request.copies // labels_per_sheet)  # Ceiling division
        
        # Save uploaded file
        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")
        
        # Run pdfcpu nup with calculated grid
        result = await pdfcpu.nup(
            input_path=input_path,
            output_path=output_path,
            grid=labels_per_sheet,
            page_size=f"{request.sheet_width_mm}x{request.sheet_height_mm}mm"
        )
        
        return ImpositionResponse(
            success=True,
            message=f"Created {columns}x{rows} step-repeat ({labels_per_sheet} per sheet, {sheets_needed} sheets for {request.copies} copies)",
            output_file_id=output_id,
            pages_created=sheets_needed,
            items_per_page=labels_per_sheet
        )
        
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        await file_manager.cleanup(input_path)

@router.get("/download/{file_id}")
async def download_imposition(file_id: str):
    """Download processed imposition PDF."""
    file_manager = FileManager()
    file_path = file_manager.get_temp_path(f"{file_id}.pdf")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"imposition_{file_id}.pdf"
    )

