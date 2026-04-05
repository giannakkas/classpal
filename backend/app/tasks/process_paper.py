"""
Celery task: Process an uploaded paper.

Pipeline:
1. Download original image from R2
2. Check image quality
3. Preprocess (perspective correction, cleanup)
4. Upload processed image to R2
5. Send to AI grading
6. Convert grading result to annotations
7. Save results to database
"""

import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.tasks.celery_app import celery_app
from app.core.config import get_settings
from app.models.school import Paper, Assignment
from app.services.image_processing import preprocess_paper, check_image_quality
from app.services.grading import grade_paper, grading_result_to_annotations
from app.services.storage import download_file_from_r2, upload_file_to_r2

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync engine for Celery tasks (Celery doesn't support async)
sync_engine = create_engine(settings.sync_database_url)
SyncSession = sessionmaker(bind=sync_engine)


def _url_to_key(url: str) -> str:
    """Extract storage key from URL (works for both R2 and local files)."""
    if url.startswith("/local-files/"):
        return url.replace("/local-files/", "", 1)
    return url.replace(f"{settings.r2_public_url}/", "")


@celery_app.task(name="app.tasks.process_paper.process_paper_task", bind=True, max_retries=2)
def process_paper_task(self, paper_id: str):
    """Process an uploaded paper: cleanup image → AI grading → save results."""
    session = SyncSession()

    try:
        paper = session.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            logger.error(f"Paper {paper_id} not found")
            return

        paper.processing_status = "processing"
        paper.processing_started_at = datetime.now(timezone.utc)
        session.commit()

        # Step 1: Download original image
        logger.info(f"Processing paper {paper_id}...")
        key = _url_to_key(paper.original_image_url)
        image_bytes = download_file_from_r2(key)

        # Step 2: Check quality
        quality = check_image_quality(image_bytes)
        if not quality["ok"]:
            paper.processing_status = "failed"
            paper.ocr_result = {"error": quality["reason"]}
            session.commit()
            logger.warning(f"Paper {paper_id} failed quality check: {quality['reason']}")
            return

        # Step 3: Preprocess image
        logger.info(f"Preprocessing paper {paper_id}...")
        processed_bytes = preprocess_paper(image_bytes)

        # Step 4: Upload processed image
        processed_key = f"papers/{paper.teacher_id}/{paper_id}/processed.jpg"
        # Run upload synchronously (boto3 is sync)
        import asyncio
        loop = asyncio.new_event_loop()
        processed_url = loop.run_until_complete(
            upload_file_to_r2(processed_bytes, processed_key, "image/jpeg")
        )
        loop.close()

        paper.processed_image_url = processed_url

        # Step 5: Get answer key if assignment has one
        answer_key_data = None
        answer_key_image_bytes = None

        if paper.assignment_id:
            assignment = session.query(Assignment).filter(
                Assignment.id == paper.assignment_id
            ).first()

            if assignment:
                if assignment.answer_key_data:
                    answer_key_data = assignment.answer_key_data
                elif assignment.answer_key_url:
                    # Download answer key image
                    try:
                        ak_key = _url_to_key(assignment.answer_key_url)
                        answer_key_image_bytes = download_file_from_r2(ak_key)
                    except Exception as e:
                        logger.warning(f"Failed to download answer key: {e}")

        # Step 6: AI Grading
        logger.info(f"Grading paper {paper_id}...")
        loop = asyncio.new_event_loop()
        grading_result = loop.run_until_complete(
            grade_paper(processed_bytes, answer_key_data, answer_key_image_bytes)
        )
        loop.close()

        # Step 7: Convert to annotations
        annotations = grading_result_to_annotations(
            grading_result, paper.correction_style
        )

        # Step 8: Save results
        paper.ocr_result = grading_result
        paper.evaluation_result = grading_result
        paper.annotations = annotations
        paper.total_score = grading_result.get("total_score")
        paper.max_score = grading_result.get("max_score")
        paper.ai_confidence = grading_result.get("ocr_confidence")

        if paper.total_score and paper.max_score and float(paper.max_score) > 0:
            paper.percentage = round(float(paper.total_score) / float(paper.max_score) * 100, 1)

        paper.processing_status = "reviewed"
        paper.processing_completed_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(
            f"Paper {paper_id} processed successfully. "
            f"Score: {paper.total_score}/{paper.max_score}, "
            f"Questions: {len(grading_result.get('questions', []))}"
        )

    except Exception as e:
        logger.error(f"Failed to process paper {paper_id}: {e}", exc_info=True)
        try:
            paper.processing_status = "failed"
            paper.ocr_result = {"error": str(e)}
            session.commit()
        except Exception:
            session.rollback()

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))

    finally:
        session.close()
