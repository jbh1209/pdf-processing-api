from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import base64
import io
import math
import time
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


class LabelImposeRequest(BaseModel):
    dieline: LabelDieline
    slots: List[LabelSlot]
    meters: float = 1.0
    include_dielines: bool = False
    return_base64: bool = True


class LabelImposeResponse(BaseModel):
    success: bool
    production_pdf_base64: str
    proof_pdf_base64: Optional[str] = None
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
        columns = int((request.sheet_width_mm - request.horizontal_gap_mm) /
                       (request.label_width_mm + request.horizontal_gap_mm))
        rows = int((request.sheet_height_mm - request.vertical_gap_mm) /
                    (request.label_height_mm + request.vertical_gap_mm))

        labels_per_sheet = columns * rows
        sheets_needed = -(-request.copies // labels_per_sheet)

        input_path = await file_manager.save_upload(file)
        output_id = str(uuid.uuid4())
        output_path = file_manager.get_temp_path(f"{output_id}.pdf")

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


# =============================================================================
# LABEL IMPOSITION ENDPOINT (called by Supabase label-impose edge function)
# =============================================================================

async def _download_pdf(url: str) -> bytes:
    """Download a PDF from a URL (Supabase signed URL)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _get_source_page(pdf_bytes: bytes) -> PageObject:
    """Read first page from PDF bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return reader.pages[0]


@router.post("/labels", response_model=LabelImposeResponse)
async def impose_labels(request: LabelImposeRequest):
    """
    Create imposed label PDF for HP Indigo roll printing.

    Accepts JSON with dieline config, slot assignments (each with a pdf_url),
    and meters to print. Returns base64-encoded production and optional proof PDFs.
    """
    start = time.time()
    d = request.dieline

    # Convert dieline dimensions to PDF points
    label_w_pt = d.label_width_mm * MM_TO_PT
    label_h_pt = d.label_height_mm * MM_TO_PT
    h_gap_pt = d.horizontal_gap_mm * MM_TO_PT
    v_gap_pt = d.vertical_gap_mm * MM_TO_PT
    roll_w_pt = d.roll_width_mm * MM_TO_PT

    # Frame height = one repeat of all rows
    frame_h_pt = (d.rows_around * label_h_pt) + ((d.rows_around - 1) * v_gap_pt)
    frame_h_mm = frame_h_pt / MM_TO_PT

    # How many frames needed to reach requested meters
    if frame_h_mm <= 0:
        raise HTTPException(status_code=400, detail="Invalid dieline dimensions")

    frame_count = max(1, math.ceil((request.meters * 1000) / frame_h_mm))
    total_meters = round((frame_count * frame_h_mm) / 1000, 3)

    # Total slots per frame
    slots_per_frame = d.columns_across * d.rows_around

    # Download all unique PDFs
    unique_urls = {s.pdf_url for s in request.slots if s.pdf_url}
    pdf_cache: dict[str, bytes] = {}

    for url in unique_urls:
        try:
            pdf_cache[url] = await _download_pdf(url)
        except Exception as e:
            print(f"Failed to download PDF: {url} — {e}")
            raise HTTPException(status_code=422, detail=f"Failed to download artwork: {e}")

    # Build slot-to-page mapping (slot numbers are 1-based, row-major)
    slot_map: dict[int, LabelSlot] = {s.slot: s for s in request.slots}

    # Create production PDF
    prod_writer = PdfWriter()

    for frame_idx in range(frame_count):
        # Create blank page for this frame
        frame_page = PageObject.create_blank_page(width=roll_w_pt, height=frame_h_pt)

        for row in range(d.rows_around):
            for col in range(d.columns_across):
                slot_num = row * d.columns_across + col + 1
                slot_info = slot_map.get(slot_num)

                if not slot_info or not slot_info.pdf_url or slot_info.pdf_url not in pdf_cache:
                    continue

                source_page = _get_source_page(pdf_cache[slot_info.pdf_url])

                # Get source dimensions
                src_w = float(source_page.mediabox.width)
                src_h = float(source_page.mediabox.height)

                # Determine rotation
                rotation = slot_info.rotation or (90 if slot_info.needs_rotation else 0)

                # Calculate position (bottom-left origin, rows go bottom to top)
                x = col * (label_w_pt + h_gap_pt)
                y = frame_h_pt - (row + 1) * label_h_pt - row * v_gap_pt

                # Build transformation
                if rotation == 90:
                    # After 90° rotation, width/height swap
                    scale_x = label_w_pt / src_h if src_h else 1
                    scale_y = label_h_pt / src_w if src_w else 1
                    op = Transformation().scale(scale_x, scale_y).rotate(90).translate(x + label_w_pt, y)
                elif rotation == 180:
                    scale_x = label_w_pt / src_w if src_w else 1
                    scale_y = label_h_pt / src_h if src_h else 1
                    op = Transformation().scale(scale_x, scale_y).rotate(180).translate(x + label_w_pt, y + label_h_pt)
                elif rotation == 270:
                    scale_x = label_w_pt / src_h if src_h else 1
                    scale_y = label_h_pt / src_w if src_w else 1
                    op = Transformation().scale(scale_x, scale_y).rotate(270).translate(x, y + label_h_pt)
                else:
                    scale_x = label_w_pt / src_w if src_w else 1
                    scale_y = label_h_pt / src_h if src_h else 1
                    op = Transformation().scale(scale_x, scale_y).translate(x, y)

                frame_page.merge_transformed_page(source_page, op)

        prod_writer.add_page(frame_page)

    # Write production PDF to bytes
    prod_buf = io.BytesIO()
    prod_writer.write(prod_buf)
    prod_bytes = prod_buf.getvalue()
    prod_b64 = base64.b64encode(prod_bytes).decode("ascii")

    # Build proof PDF with dieline overlays if requested
    proof_b64 = None
    if request.include_dielines:
        try:
            from reportlab.lib.units import mm as rl_mm
            from reportlab.lib.colors import red
            from reportlab.pdfgen import canvas as rl_canvas

            proof_writer = PdfWriter()
            # Re-read production pages and overlay dielines
            prod_reader = PdfReader(io.BytesIO(prod_bytes))

            for page in prod_reader.pages:
                # Create dieline overlay
                overlay_buf = io.BytesIO()
                c = rl_canvas.Canvas(overlay_buf, pagesize=(roll_w_pt, frame_h_pt))
                c.setStrokeColor(red)
                c.setLineWidth(0.5)

                for row in range(d.rows_around):
                    for col in range(d.columns_across):
                        x = col * (label_w_pt + h_gap_pt)
                        y = frame_h_pt - (row + 1) * label_h_pt - row * v_gap_pt

                        if d.corner_radius_mm and d.corner_radius_mm > 0:
                            r_pt = d.corner_radius_mm * MM_TO_PT
                            c.roundRect(x, y, label_w_pt, label_h_pt, r_pt, stroke=1, fill=0)
                        else:
                            c.rect(x, y, label_w_pt, label_h_pt, stroke=1, fill=0)

                c.save()
                overlay_buf.seek(0)

                overlay_reader = PdfReader(overlay_buf)
                overlay_page = overlay_reader.pages[0]

                page.merge_page(overlay_page)
                proof_writer.add_page(page)

            proof_buf = io.BytesIO()
            proof_writer.write(proof_buf)
            proof_b64 = base64.b64encode(proof_buf.getvalue()).decode("ascii")
        except ImportError:
            print("reportlab not installed — skipping proof overlay")
        except Exception as e:
            print(f"Proof overlay error: {e}")

    elapsed = round((time.time() - start) * 1000)
    print(f"Label imposition: {frame_count} frames, {total_meters}m, {elapsed}ms")

    return LabelImposeResponse(
        success=True,
        production_pdf_base64=prod_b64,
        proof_pdf_base64=proof_b64,
        frame_count=frame_count,
        total_meters=total_meters,
    )
