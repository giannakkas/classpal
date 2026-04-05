from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.usage import check_paper_quota
from app.core.config import get_settings
from app.models.user import User
from app.models.school import Paper, Assignment
from app.schemas.models import (
    PaperResponse, PaperUpdateAnnotations, PaperStatusResponse,
)
from app.services.storage import upload_file_to_r2, download_file_from_r2
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/papers", tags=["papers"])

# Sync DB for background processing (BackgroundTasks runs in threadpool)
sync_engine = create_engine(settings.sync_database_url)
SyncSession = sessionmaker(bind=sync_engine)


def process_paper_inline(paper_id: str):
    """Process a paper synchronously (runs in BackgroundTasks threadpool)."""
    from app.services.image_processing import preprocess_paper, check_image_quality
    from app.services.grading import grade_paper, grading_result_to_annotations
    import asyncio

    session = SyncSession()
    try:
        paper = session.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            logger.error(f"Paper {paper_id} not found")
            return

        paper.processing_status = "processing"
        paper.processing_started_at = datetime.now(timezone.utc)
        session.commit()

        # Download original image
        from app.services.storage import is_r2_configured
        url = paper.original_image_url
        if url.startswith("/local-files/"):
            key = url.replace("/local-files/", "", 1)
        else:
            key = url.replace(f"{settings.r2_public_url}/", "")

        image_bytes = download_file_from_r2(key)
        logger.info(f"Downloaded image for paper {paper_id}: {len(image_bytes)} bytes")

        # Check quality
        quality = check_image_quality(image_bytes)
        if not quality["ok"]:
            paper.processing_status = "failed"
            paper.ocr_result = {"error": quality["reason"]}
            session.commit()
            logger.warning(f"Paper {paper_id} failed quality: {quality['reason']}")
            return

        # Preprocess
        logger.info(f"Preprocessing paper {paper_id}...")
        processed_bytes = preprocess_paper(image_bytes)

        # Upload processed image
        processed_key = f"papers/{paper.teacher_id}/{paper_id}/processed.jpg"
        loop = asyncio.new_event_loop()
        processed_url = loop.run_until_complete(
            upload_file_to_r2(processed_bytes, processed_key, "image/jpeg")
        )
        loop.close()
        paper.processed_image_url = processed_url

        # Get answer key if available
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
                    try:
                        ak_key = assignment.answer_key_url
                        if ak_key.startswith("/local-files/"):
                            ak_key = ak_key.replace("/local-files/", "", 1)
                        else:
                            ak_key = ak_key.replace(f"{settings.r2_public_url}/", "")
                        answer_key_image_bytes = download_file_from_r2(ak_key)
                    except Exception as e:
                        logger.warning(f"Failed to download answer key: {e}")

        # AI Grading
        logger.info(f"Grading paper {paper_id} with Claude Vision...")
        loop = asyncio.new_event_loop()
        grading_result = loop.run_until_complete(
            grade_paper(processed_bytes, answer_key_data, answer_key_image_bytes)
        )
        loop.close()

        # Convert to annotations
        annotations = grading_result_to_annotations(grading_result, paper.correction_style)

        # Save results
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
            f"Paper {paper_id} processed! Score: {paper.total_score}/{paper.max_score}, "
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
    finally:
        session.close()


@router.post("/upload", response_model=PaperResponse, status_code=201)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    assignment_id: str | None = Form(None),
    student_id: str | None = Form(None),
    correction_style: str = Form("red_pen"),
    user: User = Depends(check_paper_quota),
    db: AsyncSession = Depends(get_db),
):
    # Validate file
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed. Use JPEG, PNG, or WebP.",
        )

    contents = await file.read()
    file_size = len(contents)
    if file_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    # Upload original to R2
    import uuid
    paper_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    key = f"papers/{user.id}/{paper_id}/original.{ext}"
    url = await upload_file_to_r2(contents, key, file.content_type)

    # Create paper record
    paper = Paper(
        id=paper_id,
        teacher_id=user.id,
        assignment_id=assignment_id,
        student_id=student_id,
        original_image_url=url,
        original_image_size=file_size,
        correction_style=correction_style,
        processing_status="pending",
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    # Process paper in background (same server, no Celery needed for local storage)
    background_tasks.add_task(process_paper_inline, paper_id)

    return paper


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.teacher_id == user.id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/{paper_id}/status", response_model=PaperStatusResponse)
async def get_paper_status(
    paper_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.teacher_id == user.id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperStatusResponse(
        id=paper.id,
        processing_status=paper.processing_status,
        ai_confidence=float(paper.ai_confidence) if paper.ai_confidence else None,
    )


@router.put("/{paper_id}/annotations", response_model=PaperResponse)
async def update_annotations(
    paper_id: str,
    req: PaperUpdateAnnotations,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.teacher_id == user.id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper.annotations = [a.model_dump() for a in req.annotations]
    if req.total_score is not None:
        paper.total_score = req.total_score
    if req.max_score is not None:
        paper.max_score = req.max_score
    if req.teacher_feedback is not None:
        paper.teacher_feedback = req.teacher_feedback
    if req.correction_style is not None:
        paper.correction_style = req.correction_style

    # Calculate percentage
    if paper.total_score is not None and paper.max_score and float(paper.max_score) > 0:
        paper.percentage = round(float(paper.total_score) / float(paper.max_score) * 100, 1)

    paper.processing_status = "corrected"
    await db.commit()
    await db.refresh(paper)
    return paper


@router.post("/{paper_id}/finalize", response_model=PaperResponse)
async def finalize_paper(
    paper_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.teacher_id == user.id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.processing_status not in ("reviewed", "corrected"):
        raise HTTPException(
            status_code=400,
            detail="Paper must be reviewed/corrected before finalizing",
        )

    # Dispatch PDF generation task
    celery_app.send_task(
        "app.tasks.generate_pdf.generate_pdf_task",
        args=[paper_id],
    )

    paper.processing_status = "finalized"
    await db.commit()
    await db.refresh(paper)
    return paper


@router.get("", response_model=list[PaperResponse])
async def list_papers(
    assignment_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Paper).where(Paper.teacher_id == user.id)
    if assignment_id:
        query = query.where(Paper.assignment_id == assignment_id)
    if status:
        query = query.where(Paper.processing_status == status)
    query = query.order_by(Paper.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()
