import pikepdf
from pathlib import Path
import logging
from typing import Optional

from app.utils.exceptions import PDFProcessingError

logger = logging.getLogger(__name__)

class PikepdfService:
    
    async def full_preflight(self, input_path: Path, min_dpi: float = 300) -> dict:
        """Comprehensive preflight check."""
        
        try:
            with pikepdf.open(input_path) as pdf:
                report = {
                    "page_count": len(pdf.pages),
                    "pdf_version": str(pdf.pdf_version),
                    "page_boxes": [],
                    "has_bleed": False,
                    "bleed_mm": None,
                    "images": [],
                    "low_res_images": 0,
                    "min_dpi": None,
                    "fonts": [],
                    "unembedded_fonts": 0,
                    "color_spaces": [],
                    "has_rgb": False,
                    "has_cmyk": False,
                    "spot_colors": [],
                    "warnings": [],
                    "errors": []
                }
                
                # Check page boxes
                for i, page in enumerate(pdf.pages):
                    box_info = self._get_page_boxes(page)
                    report["page_boxes"].append(box_info)
                    
                    # Check for bleed
                    if box_info.get("bleed_box") and box_info.get("trim_box"):
                        bleed = box_info["bleed_box"]
                        trim = box_info["trim_box"]
                        # Calculate bleed amount (simplified)
                        bleed_amount = abs(bleed[0] - trim[0]) / 2.835  # Convert to mm
                        if bleed_amount > 0:
                            report["has_bleed"] = True
                            report["bleed_mm"] = round(bleed_amount, 2)
                
                # Check fonts
                fonts = self._get_fonts(pdf)
                report["fonts"] = fonts
                report["unembedded_fonts"] = sum(1 for f in fonts if not f.get("embedded"))
                
                if report["unembedded_fonts"] > 0:
                    report["errors"].append(f"{report['unembedded_fonts']} fonts are not embedded")
                
                # Check images (simplified - full implementation would iterate all XObjects)
                # This is a placeholder for the full image analysis
                
                # Check color spaces
                color_spaces = self._get_color_spaces(pdf)
                report["color_spaces"] = list(color_spaces)
                report["has_rgb"] = any("RGB" in cs for cs in color_spaces)
                report["has_cmyk"] = any("CMYK" in cs for cs in color_spaces)
                
                if report["has_rgb"]:
                    report["warnings"].append("PDF contains RGB color space - may need conversion")
                
                return report
                
        except Exception as e:
            logger.error(f"Preflight error: {e}")
            raise PDFProcessingError(f"Preflight check failed: {str(e)}")
    
    def _get_page_boxes(self, page) -> dict:
        """Extract page box information."""
        boxes = {}
        
        if "/MediaBox" in page:
            boxes["media_box"] = list(page.MediaBox)
        
        if "/TrimBox" in page:
            boxes["trim_box"] = list(page.TrimBox)
        
        if "/BleedBox" in page:
            boxes["bleed_box"] = list(page.BleedBox)
        
        if "/ArtBox" in page:
            boxes["art_box"] = list(page.ArtBox)
        
        return boxes

        async def get_page_boxes_detailed(self, input_path: Path) -> dict:
        """
        Extract detailed page box information with dimensions.
        
        Returns all page boxes from the first page with x1, y1, x2, y2, width, height.
        All values are in PDF points (1 pt = 1/72 inch = 0.3528 mm).
        """
        try:
            with pikepdf.open(input_path) as pdf:
                if len(pdf.pages) == 0:
                    raise PDFProcessingError("PDF has no pages")
                
                page = pdf.pages[0]
                
                def box_to_dict(box_array) -> dict | None:
                    """Convert pikepdf box array [x1, y1, x2, y2] to dict with dimensions."""
                    if box_array is None:
                        return None
                    try:
                        # Convert pikepdf objects to floats
                        coords = [float(x) for x in box_array]
                        if len(coords) != 4:
                            return None
                        x1, y1, x2, y2 = coords
                        return {
                            "x1": round(x1, 2),
                            "y1": round(y1, 2),
                            "x2": round(x2, 2),
                            "y2": round(y2, 2),
                            "width": round(abs(x2 - x1), 2),
                            "height": round(abs(y2 - y1), 2)
                        }
                    except (IndexError, TypeError, ValueError) as e:
                        logger.warning(f"Failed to parse box: {e}")
                        return None
                
                # Extract all boxes - MediaBox is always present
                result = {
                    "mediabox": box_to_dict(page.MediaBox if "/MediaBox" in page else None),
                    "cropbox": box_to_dict(page.CropBox if "/CropBox" in page else None),
                    "bleedbox": box_to_dict(page.BleedBox if "/BleedBox" in page else None),
                    "trimbox": box_to_dict(page.TrimBox if "/TrimBox" in page else None),
                    "artbox": box_to_dict(page.ArtBox if "/ArtBox" in page else None),
                }
                
                logger.info(f"Extracted page boxes: mediabox={result['mediabox']}, trimbox={result['trimbox']}")
                return result
                
        except pikepdf.PdfError as e:
            logger.error(f"PDF parsing error: {e}")
            raise PDFProcessingError(f"Failed to parse PDF: {str(e)}")
        except Exception as e:
            logger.error(f"Page boxes extraction error: {e}")
            raise PDFProcessingError(f"Failed to extract page boxes: {str(e)}")

    
    def _get_fonts(self, pdf) -> list:
        """Extract font information."""
        fonts = []
        seen = set()
        
        for page in pdf.pages:
            if "/Resources" not in page:
                continue
            resources = page.Resources
            if "/Font" not in resources:
                continue
            
            for font_name, font_ref in resources.Font.items():
                if str(font_name) in seen:
                    continue
                seen.add(str(font_name))
                
                try:
                    font = font_ref
                    font_info = {
                        "name": str(font_name),
                        "subtype": str(font.get("/Subtype", "Unknown")),
                        "embedded": "/FontFile" in font or "/FontFile2" in font or "/FontFile3" in font,
                        "subset": "+" in str(font.get("/BaseFont", ""))
                    }
                    fonts.append(font_info)
                except:
                    pass
        
        return fonts
    
    def _get_color_spaces(self, pdf) -> set:
        """Extract color spaces used in PDF."""
        color_spaces = set()
        
        for page in pdf.pages:
            if "/Resources" not in page:
                continue
            resources = page.Resources
            if "/ColorSpace" in resources:
                for cs_name, cs_value in resources.ColorSpace.items():
                    color_spaces.add(str(cs_name))
        
        return color_spaces
    
    async def get_spot_colors(self, input_path: Path) -> list:
        """Extract spot/separation colors from PDF."""
        spot_colors = []
        
        try:
            with pikepdf.open(input_path) as pdf:
                for page in pdf.pages:
                    if "/Resources" not in page:
                        continue
                    resources = page.Resources
                    if "/ColorSpace" not in resources:
                        continue
                    
                    for cs_name, cs_value in resources.ColorSpace.items():
                        # Look for Separation color spaces
                        if isinstance(cs_value, pikepdf.Array):
                            if len(cs_value) > 0 and str(cs_value[0]) == "/Separation":
                                if len(cs_value) > 1:
                                    spot_name = str(cs_value[1])
                                    if spot_name not in spot_colors:
                                        spot_colors.append(spot_name)
            
            return spot_colors
            
        except Exception as e:
            logger.error(f"Spot color extraction error: {e}")
            raise PDFProcessingError(f"Failed to extract spot colors: {str(e)}")
    
    async def check_images(self, input_path: Path, min_dpi: float) -> list:
        """Check image resolution in PDF."""
        images = []
        
        try:
            with pikepdf.open(input_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if "/Resources" not in page:
                        continue
                    resources = page.Resources
                    if "/XObject" not in resources:
                        continue
                    
                    for xobj_name, xobj_ref in resources.XObject.items():
                        try:
                            xobj = xobj_ref
                            if xobj.get("/Subtype") != "/Image":
                                continue
                            
                            width = int(xobj.get("/Width", 0))
                            height = int(xobj.get("/Height", 0))
                            
                            # Estimate DPI (simplified - would need transformation matrix for accuracy)
                            media_box = list(page.MediaBox)
                            page_width_pts = float(media_box[2] - media_box[0])
                            estimated_dpi = (width / page_width_pts) * 72 if page_width_pts > 0 else 0
                            
                            color_space = str(xobj.get("/ColorSpace", "Unknown"))
                            
                            images.append({
                                "page": page_num,
                                "width": width,
                                "height": height,
                                "color_space": color_space,
                                "bits_per_component": int(xobj.get("/BitsPerComponent", 8)),
                                "estimated_dpi": round(estimated_dpi, 1),
                                "is_low_res": estimated_dpi < min_dpi if estimated_dpi > 0 else False
                            })
                        except:
                            pass
            
            return images
            
        except Exception as e:
            logger.error(f"Image check error: {e}")
            raise PDFProcessingError(f"Failed to check images: {str(e)}")

