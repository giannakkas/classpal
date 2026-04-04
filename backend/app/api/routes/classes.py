from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.school import Class, Student, class_students
from app.schemas.models import ClassCreate, ClassUpdate, ClassResponse

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("", response_model=list[ClassResponse])
async def list_classes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.teacher_id == user.id, Class.is_archived == False)
    )
    classes = result.scalars().all()
    return [
        ClassResponse(
            **{c: getattr(cls, c) for c in ["id", "name", "subject", "grade_level", "academic_year", "is_archived", "created_at"]},
            student_count=len(cls.students),
        )
        for cls in classes
    ]


@router.post("", response_model=ClassResponse, status_code=201)
async def create_class(
    req: ClassCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = Class(teacher_id=user.id, **req.model_dump())
    db.add(cls)
    await db.commit()
    await db.refresh(cls)
    return ClassResponse(
        id=cls.id, name=cls.name, subject=cls.subject,
        grade_level=cls.grade_level, academic_year=cls.academic_year,
        is_archived=cls.is_archived, student_count=0, created_at=cls.created_at,
    )


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.id == class_id, Class.teacher_id == user.id)
    )
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return ClassResponse(
        id=cls.id, name=cls.name, subject=cls.subject,
        grade_level=cls.grade_level, academic_year=cls.academic_year,
        is_archived=cls.is_archived, student_count=len(cls.students),
        created_at=cls.created_at,
    )


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    req: ClassUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.id == class_id, Class.teacher_id == user.id)
    )
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(cls, key, value)

    await db.commit()
    await db.refresh(cls)
    return ClassResponse(
        id=cls.id, name=cls.name, subject=cls.subject,
        grade_level=cls.grade_level, academic_year=cls.academic_year,
        is_archived=cls.is_archived, student_count=len(cls.students),
        created_at=cls.created_at,
    )


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.id == class_id, Class.teacher_id == user.id)
    )
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    await db.delete(cls)
    await db.commit()


@router.post("/{class_id}/students/{student_id}", status_code=201)
async def add_student_to_class(
    class_id: str,
    student_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership of both class and student
    cls_result = await db.execute(
        select(Class).where(Class.id == class_id, Class.teacher_id == user.id)
    )
    cls = cls_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    stu_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Check if already in class
    if student in cls.students:
        raise HTTPException(status_code=409, detail="Student already in class")

    cls.students.append(student)
    await db.commit()
    return {"message": "Student added to class"}


@router.delete("/{class_id}/students/{student_id}", status_code=204)
async def remove_student_from_class(
    class_id: str,
    student_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls_result = await db.execute(
        select(Class).where(Class.id == class_id, Class.teacher_id == user.id)
    )
    cls = cls_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    stu_result = await db.execute(
        select(Student).where(Student.id == student_id, Student.teacher_id == user.id)
    )
    student = stu_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student in cls.students:
        cls.students.remove(student)
        await db.commit()
