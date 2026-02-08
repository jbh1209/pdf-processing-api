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
                page_count = len(pdf.pages)

                if page_count == 0:
                    raise PDFProcessingError("PDF has no pages")

                first_page = pdf.pages[0]
                page_boxes = self._get_page_boxes(first_page)

                fonts = self._get_fonts(pdf)
                color_spaces = list(self._get_color_spaces(pdf))

                images = await self.check_images(input_path, min_dpi)
                spot_colors = await self.get_spot_colors(input_path)

                return {
                    "page_count": page_count,
                    "page_boxes": page_boxes,
                    "fonts": fonts,
                    "color_spaces": color_spaces,
                    "images": images,
                    "spot_colors": spot_colors,
                    "is_encrypted": pdf.is_encrypted,
                    "pdf_version": str(pdf.pdf_version),
                }

        except pikepdf.PdfError as e:
            logger.error(f"PDF parsing error: {e}")
            raise PDFProcessingError(f"Failed to parse PDF: {str(e)}")
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
        """Extract font information from PDF."""
        fonts = []
        for page in pdf.pages:
            if "/Resources" in page:
                resources = page.Resources
                if "/Font" in resources:
                    for font_name, font_obj in resources.Font.items():
                        try:
                            font_info = {
                                "name": str(font_name),
                                "subtype": str(font_obj.Subtype) if "/Subtype" in font_obj else "Unknown",
                                "embedded": "/FontFile" in font_obj or "/FontFile2" in font_obj or "/FontFile3" in font_obj
                            }
                            if font_info not in fonts:
                                fonts.append(font_info)
                        except Exception as e:
                            logger.warning(f"Could not extract font info: {e}")
        return fonts

    def _get_color_spaces(self, pdf) -> set:
        """Extract color space information from PDF."""
        color_spaces = set()

        for page in pdf.pages:
            if "/Resources" in page:
                resources = page.Resources
                if "/ColorSpace" in resources:
                    for cs_name, cs_obj in resources.ColorSpace.items():
                        try:
                            if isinstance(cs_obj, pikepdf.Array):
                                color_spaces.add(str(cs_obj[0]))
                            else:
                                color_spaces.add(str(cs_obj))
                        except Exception as e:
                            logger.warning(f"Could not extract colorspace: {e}")

        return color_spaces

    async def get_spot_colors(self, input_path: Path) -> list:
        """Extract spot/separation colors from PDF."""
        spot_colors = []

        try:
            with pikepdf.open(input_path) as pdf:
                for page in pdf.pages:
                    if "/Resources" in page:
                        resources = page.Resources
                        if "/ColorSpace" in resources:
                            for cs_name, cs_obj in resources.ColorSpace.items():
                                if isinstance(cs_obj, pikepdf.Array):
                                    cs_type = str(cs_obj[0])
                                    if cs_type == "/Separation" and len(cs_obj) > 1:
                                        spot_name = str(cs_obj[1])
                                        if spot_name not in spot_colors:
                                            spot_colors.append(spot_name)
        except Exception as e:
            logger.warning(f"Could not extract spot colors: {e}")

        return spot_colors

    async def check_images(self, input_path: Path, min_dpi: float = 300) -> list:
        """Check image resolution in PDF."""
        images = []

        try:
            with pikepdf.open(input_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if "/Resources" in page:
                        resources = page.Resources
                        if "/XObject" in resources:
                            for xobj_name, xobj in resources.XObject.items():
                                if xobj.Subtype == pikepdf.Name.Image:
                                    try:
                                        width = int(xobj.Width)
                                        height = int(xobj.Height)

                                        image_info = {
                                            "page": page_num + 1,
                                            "name": str(xobj_name),
                                            "width": width,
                                            "height": height,
                                            "color_space": str(xobj.ColorSpace) if "/ColorSpace" in xobj else "Unknown",
                                            "bits_per_component": int(xobj.BitsPerComponent) if "/BitsPerComponent" in xobj else None
                                        }
                                        images.append(image_info)
                                    except Exception as e:
                                        logger.warning(f"Could not extract image info: {e}")
        except Exception as e:
            logger.warning(f"Could not check images: {e}")

        return images
