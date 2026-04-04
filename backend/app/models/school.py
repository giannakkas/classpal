import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, Integer, Text, Date, Table, Column, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# Many-to-many: students <-> classes
class_students = Table(
    "class_students",
    Base.metadata,
    Column("class_id", String(36), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", String(36), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
)


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    teacher = relationship("User", back_populates="classes")
    students = relationship("Student", secondary=class_students, back_populates="classes", lazy="selectin")
    assignments = relationship("Assignment", back_populates="class_", lazy="selectin")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    teacher = relationship("User", back_populates="students")
    classes = relationship("Class", secondary=class_students, back_populates="students")
    papers = relationship("Paper", back_populates="student", lazy="selectin")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=False, index=True
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    answer_key_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_key_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grading_rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    class_ = relationship("Class", back_populates="assignments")
    papers = relationship("Paper", back_populates="assignment", lazy="selectin")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assignments.id"), nullable=True, index=True
    )
    student_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("students.id"), nullable=True, index=True
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )

    # Original upload
    original_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    original_image_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Processed image
    processed_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI results
    ocr_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending, processing, reviewed, corrected, finalized, failed

    # Corrections
    annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correction_style: Mapped[str] = mapped_column(String(20), default="red_pen")

    # Scores
    total_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Final output
    corrected_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    assignment = relationship("Assignment", back_populates="papers")
    student = relationship("Student", back_populates="papers")
