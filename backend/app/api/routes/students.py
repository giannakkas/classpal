from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.school import Student, Paper
from app.schemas.models import StudentCreate, StudentUpdate, StudentResponse, PaperResponse

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentResponse])
async def list_students(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Student).where(Student.teacher_id == user.id).order_by(Student.full_name)
    )
    return result.scalars().all()


@router.post("", response_model=StudentResponse, status_code=201)
async def create_student(
    req: StudentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    student = Student(teacher_id=user.id, **req.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    req: StudentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(student, key, value)

    await db.commit()
    await db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.delete(student)
    await db.commit()


@router.get("/{student_id}/papers", response_model=list[PaperResponse])
async def list_student_papers(
    student_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify student belongs to this teacher
    stu_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    if not stu_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Student not found")

    result = await db.execute(
        select(Paper)
        .where(Paper.student_id == student_id, Paper.teacher_id == user.id)
        .order_by(Paper.created_at.desc())
    )
    return result.scalars().all()
