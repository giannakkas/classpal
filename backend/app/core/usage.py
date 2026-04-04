"""
Usage limits — checks if the teacher has papers remaining in their plan.
Use as a FastAPI dependency on the paper upload route.
"""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.school import Paper

TIER_LIMITS = {
    "free": 20,
    "solo": 100,
    "pro": 500,
    "school": 300,  # per teacher
}


async def check_paper_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: raises 429 if teacher has exceeded their monthly paper limit."""
    limit = TIER_LIMITS.get(user.subscription_tier, 20)

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(Paper.id)).where(
            Paper.teacher_id == user.id,
            Paper.created_at >= month_start,
        )
    )
    used = result.scalar() or 0

    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly paper limit reached ({used}/{limit}). "
            f"Upgrade your plan for more papers.",
        )

    return user
