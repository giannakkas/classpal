from pydantic import BaseModel
from datetime import datetime, date


# --- Classes ---

class ClassCreate(BaseModel):
    name: str
    subject: str | None = None
    grade_level: str | None = None
    academic_year: str | None = None


class ClassUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    grade_level: str | None = None
    academic_year: str | None = None
    is_archived: bool | None = None


class ClassResponse(BaseModel):
    id: str
    name: str
    subject: str | None
    grade_level: str | None
    academic_year: str | None
    is_archived: bool
    student_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# --- Students ---

class StudentCreate(BaseModel):
    full_name: str
    student_number: str | None = None
    parent_email: str | None = None
    notes: str | None = None


class StudentUpdate(BaseModel):
    full_name: str | None = None
    student_number: str | None = None
    parent_email: str | None = None
    notes: str | None = None


class StudentResponse(BaseModel):
    id: str
    full_name: str
    student_number: str | None
    parent_email: str | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Assignments ---

class AssignmentCreate(BaseModel):
    class_id: str
    title: str
    description: str | None = None
    subject: str | None = None
    max_score: float | None = None
    due_date: date | None = None


class AssignmentResponse(BaseModel):
    id: str
    class_id: str
    title: str
    description: str | None
    subject: str | None
    max_score: float | None
    due_date: date | None
    answer_key_url: str | None
    paper_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# --- Papers ---

class PaperUploadRequest(BaseModel):
    assignment_id: str | None = None
    student_id: str | None = None
    correction_style: str = "red_pen"


class AnnotationData(BaseModel):
    id: str
    type: str  # checkmark, xmark, circle, underline, text_note, score_box
    position: dict  # {x, y}
    bounds: dict | None = None
    style: str = "red_pen"
    text: str | None = None
    score: float | None = None
    max_score: float | None = None
    ai_generated: bool = False
    confidence: float = 1.0
    linked_question_id: str | None = None
    svg_path: str | None = None
    rotation: float | None = None


class PaperUpdateAnnotations(BaseModel):
    annotations: list[AnnotationData]
    total_score: float | None = None
    max_score: float | None = None
    teacher_feedback: str | None = None
    correction_style: str | None = None


class QuestionResult(BaseModel):
    number: str
    question_text: str | None = None
    student_answer: str | None = None
    correct_answer: str | None = None
    is_correct: bool | None = None
    score: float = 0
    max_score: float = 1
    confidence: float = 0
    answer_bbox: list[float] | None = None
    correction_note: str | None = None


class PaperResponse(BaseModel):
    id: str
    assignment_id: str | None
    student_id: str | None
    original_image_url: str
    processed_image_url: str | None
    processing_status: str
    correction_style: str
    annotations: list[AnnotationData] | None = None
    ocr_result: dict | None = None
    evaluation_result: dict | None = None
    ai_confidence: float | None = None
    total_score: float | None
    max_score: float | None
    percentage: float | None
    grade: str | None
    corrected_pdf_url: str | None
    teacher_feedback: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class PaperStatusResponse(BaseModel):
    id: str
    processing_status: str
    ai_confidence: float | None = None
