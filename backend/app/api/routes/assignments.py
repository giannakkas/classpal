from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.school import Assignment, Class
from app.schemas.models import AssignmentCreate, AssignmentResponse
from app.services.storage import upload_file_to_r2

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentResponse])
async def list_assignments(
    class_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Assignment).where(Assignment.teacher_id == user.id)
    if class_id:
        query = query.where(Assignment.class_id == class_id)
    query = query.order_by(Assignment.created_at.desc())

    result = await db.execute(query)
    assignments = result.scalars().all()
    return [
        AssignmentResponse(
            id=a.id, class_id=a.class_id, title=a.title,
            description=a.description, subject=a.subject,
            max_score=float(a.max_score) if a.max_score else None,
            due_date=a.due_date, answer_key_url=a.answer_key_url,
            paper_count=len(a.papers), created_at=a.created_at,
        )
        for a in assignments
    ]


@router.post("", response_model=AssignmentResponse, status_code=201)
async def create_assignment(
    req: AssignmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify class ownership
    cls_result = await db.execute(
        select(Class).where(Class.id == req.class_id, Class.teacher_id == user.id)
    )
    if not cls_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Class not found")

    assignment = Assignment(teacher_id=user.id, **req.model_dump())
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return AssignmentResponse(
        id=assignment.id, class_id=assignment.class_id, title=assignment.title,
        description=assignment.description, subject=assignment.subject,
        max_score=float(assignment.max_score) if assignment.max_score else None,
        due_date=assignment.due_date, answer_key_url=None,
        paper_count=0, created_at=assignment.created_at,
    )


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.teacher_id == user.id
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return AssignmentResponse(
        id=assignment.id, class_id=assignment.class_id, title=assignment.title,
        description=assignment.description, subject=assignment.subject,
        max_score=float(assignment.max_score) if assignment.max_score else None,
        due_date=assignment.due_date, answer_key_url=assignment.answer_key_url,
        paper_count=len(assignment.papers), created_at=assignment.created_at,
    )


@router.post("/{assignment_id}/answer-key")
async def upload_answer_key(
    assignment_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.teacher_id == user.id
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

    # Upload to R2
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    key = f"answer-keys/{user.id}/{assignment_id}/{file.filename}"
    url = await upload_file_to_r2(contents, key, file.content_type)

    assignment.answer_key_url = url
    await db.commit()

    return {"message": "Answer key uploaded", "url": url}
