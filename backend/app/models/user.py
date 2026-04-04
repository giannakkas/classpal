import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="teacher")  # teacher, school_admin, super_admin
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Subscription
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")  # free, solo, pro, school
    subscription_status: Mapped[str] = mapped_column(String(20), default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Preferences
    preferred_correction_style: Mapped[str] = mapped_column(String(20), default="red_pen")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    classes = relationship("Class", back_populates="teacher", lazy="selectin")
    students = relationship("Student", back_populates="teacher", lazy="selectin")
