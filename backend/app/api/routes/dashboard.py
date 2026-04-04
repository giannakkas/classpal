from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.school import Paper, Class, Student
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

    # Papers graded today
    graded_today = await db.execute(
        select(func.count(Paper.id)).where(
            Paper.teacher_id == user.id,
            Paper.finalized_at >= today,
        )
    )

    # Total papers pending review
    pending = await db.execute(
        select(func.count(Paper.id)).where(
            Paper.teacher_id == user.id,
            Paper.processing_status.in_(["pending", "processing", "reviewed"]),
        )
    )

    # Total classes
    class_count = await db.execute(
        select(func.count(Class.id)).where(
            Class.teacher_id == user.id, Class.is_archived == False
        )
    )

    # Total students
    student_count = await db.execute(
        select(func.count(Student.id)).where(Student.teacher_id == user.id)
    )

    # Recent papers
    recent = await db.execute(
        select(Paper)
        .where(Paper.teacher_id == user.id)
        .order_by(Paper.created_at.desc())
        .limit(10)
    )

    return {
        "papers_graded_today": graded_today.scalar() or 0,
        "papers_pending": pending.scalar() or 0,
        "total_classes": class_count.scalar() or 0,
        "total_students": student_count.scalar() or 0,
        "recent_papers": [
            {
                "id": p.id,
                "student_id": p.student_id,
                "status": p.processing_status,
                "score": float(p.total_score) if p.total_score else None,
                "max_score": float(p.max_score) if p.max_score else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in recent.scalars().all()
        ],
    }
