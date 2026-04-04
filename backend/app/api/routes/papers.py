from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.usage import check_paper_quota
from app.models.user import User
from app.models.school import Paper
from app.schemas.models import (
    PaperResponse, PaperUpdateAnnotations, PaperStatusResponse,
)
from app.services.storage import upload_file_to_r2
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/papers", tags=["papers"])


@router.post("/upload", response_model=PaperResponse, status_code=201)
async def upload_paper(
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

    # Dispatch async processing task
    celery_app.send_task(
        "app.tasks.process_paper.process_paper_task",
        args=[paper_id],
    )

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
