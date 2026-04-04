"""
Celery task: Generate corrected PDF from paper image + annotations.

Uses Pillow for image compositing + annotation rendering, then wraps in PDF.
WeasyPrint alternative can be used for HTML→PDF if needed later.
"""

import io
import logging
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.tasks.celery_app import celery_app
from app.core.config import get_settings
from app.models.school import Paper
from app.services.storage import download_file_from_r2, upload_file_to_r2

logger = logging.getLogger(__name__)
settings = get_settings()

sync_engine = create_engine(settings.sync_database_url)
SyncSession = sessionmaker(bind=sync_engine)

# Correction style colors (RGBA)
STYLE_COLORS = {
    "red_pen": (204, 34, 34, 220),
    "blue_pen": (26, 75, 140, 204),
    "pencil": (74, 74, 74, 140),
}

STYLE_WIDTHS = {
    "red_pen": 3,
    "blue_pen": 3,
    "pencil": 2,
}


def _url_to_key(url: str) -> str:
    return url.replace(f"{settings.r2_public_url}/", "")


def render_annotations_on_image(
    image_bytes: bytes, annotations: list[dict], style: str = "red_pen"
) -> bytes:
    """Render annotation objects onto the paper image. Returns PNG bytes."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    # Create transparent overlay for annotations
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    color = STYLE_COLORS.get(style, STYLE_COLORS["red_pen"])
    line_width = STYLE_WIDTHS.get(style, 3)

    # Try to load a handwriting-style font, fall back to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_score = ImageFont.load_default()

    for ann in annotations:
        pos = ann.get("position", {})
        px = int(pos.get("x", 0) * w)
        py = int(pos.get("y", 0) * h)
        ann_type = ann.get("type", "")

        if ann_type == "checkmark":
            # Draw a checkmark ✓
            points = [
                (px, py + 12),
                (px + 8, py + 20),
                (px + 22, py),
            ]
            draw.line(points, fill=color, width=line_width, joint="curve")

        elif ann_type == "xmark":
            # Draw an X
            size = 16
            draw.line([(px, py), (px + size, py + size)], fill=color, width=line_width)
            draw.line([(px + size, py), (px, py + size)], fill=color, width=line_width)

        elif ann_type == "circle":
            bounds = ann.get("bounds", {})
            bw = int(bounds.get("width", 0.05) * w)
            bh = int(bounds.get("height", 0.03) * h)
            draw.ellipse(
                [(px - 4, py - 4), (px + bw + 4, py + bh + 4)],
                outline=color, width=line_width,
            )

        elif ann_type == "underline":
            bounds = ann.get("bounds", {})
            length = int(bounds.get("width", 0.1) * w)
            draw.line([(px, py), (px + length, py)], fill=color, width=line_width)

        elif ann_type == "text_note":
            text = ann.get("text", "")
            if text:
                draw.text((px, py), text, fill=color, font=font_small)

        elif ann_type == "score_box":
            text = ann.get("text", "")
            if text:
                # Draw box around score
                bbox = draw.textbbox((px, py), text, font=font_score)
                padding = 8
                draw.rectangle(
                    [
                        (bbox[0] - padding, bbox[1] - padding),
                        (bbox[2] + padding, bbox[3] + padding),
                    ],
                    outline=color, width=line_width + 1,
                )
                draw.text((px, py), text, fill=color, font=font_score)

    # Composite overlay onto original
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")

    # Save as PDF
    pdf_bytes = io.BytesIO()
    result.save(pdf_bytes, format="PDF", resolution=150)
    pdf_bytes.seek(0)
    return pdf_bytes.read()


@celery_app.task(name="app.tasks.generate_pdf.generate_pdf_task", bind=True, max_retries=2)
def generate_pdf_task(self, paper_id: str):
    """Generate corrected PDF for a finalized paper."""
    session = SyncSession()

    try:
        paper = session.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            logger.error(f"Paper {paper_id} not found")
            return

        # Use processed image (or original if processed isn't available)
        image_url = paper.processed_image_url or paper.original_image_url
        key = _url_to_key(image_url)
        image_bytes = download_file_from_r2(key)

        annotations = paper.annotations or []

        logger.info(f"Generating PDF for paper {paper_id} with {len(annotations)} annotations...")

        # Render
        pdf_bytes = render_annotations_on_image(
            image_bytes, annotations, paper.correction_style
        )

        # Upload PDF to R2
        pdf_key = f"papers/{paper.teacher_id}/{paper_id}/corrected.pdf"

        import asyncio
        loop = asyncio.new_event_loop()
        pdf_url = loop.run_until_complete(
            upload_file_to_r2(pdf_bytes, pdf_key, "application/pdf")
        )
        loop.close()

        paper.corrected_pdf_url = pdf_url
        paper.finalized_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(f"PDF generated for paper {paper_id}: {pdf_url}")

    except Exception as e:
        logger.error(f"Failed to generate PDF for paper {paper_id}: {e}", exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
    finally:
        session.close()
