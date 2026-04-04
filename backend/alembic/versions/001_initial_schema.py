"""initial_schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), server_default='teacher'),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('school_id', sa.String(36), nullable=True),
        sa.Column('subscription_tier', sa.String(20), server_default='free'),
        sa.Column('subscription_status', sa.String(20), server_default='active'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('preferred_correction_style', sa.String(20), server_default='red_pen'),
        sa.Column('timezone', sa.String(50), server_default='UTC'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Classes
    op.create_table(
        'classes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('teacher_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(100), nullable=True),
        sa.Column('grade_level', sa.String(50), nullable=True),
        sa.Column('academic_year', sa.String(20), nullable=True),
        sa.Column('is_archived', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Students
    op.create_table(
        'students',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('teacher_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('student_number', sa.String(50), nullable=True),
        sa.Column('parent_email', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Class-Students junction
    op.create_table(
        'class_students',
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
    )

    # Assignments
    op.create_table(
        'assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=False, index=True),
        sa.Column('teacher_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('subject', sa.String(100), nullable=True),
        sa.Column('max_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('answer_key_url', sa.Text(), nullable=True),
        sa.Column('answer_key_data', sa.JSON(), nullable=True),
        sa.Column('grading_rubric', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Papers
    op.create_table(
        'papers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('assignment_id', sa.String(36), sa.ForeignKey('assignments.id'), nullable=True, index=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=True, index=True),
        sa.Column('teacher_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('original_image_url', sa.Text(), nullable=False),
        sa.Column('original_image_size', sa.Integer(), nullable=True),
        sa.Column('processed_image_url', sa.Text(), nullable=True),
        sa.Column('ocr_result', sa.JSON(), nullable=True),
        sa.Column('evaluation_result', sa.JSON(), nullable=True),
        sa.Column('ai_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('processing_status', sa.String(20), server_default='pending', index=True),
        sa.Column('annotations', sa.JSON(), nullable=True),
        sa.Column('correction_style', sa.String(20), server_default='red_pen'),
        sa.Column('total_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('max_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('grade', sa.String(10), nullable=True),
        sa.Column('corrected_pdf_url', sa.Text(), nullable=True),
        sa.Column('teacher_feedback', sa.Text(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('papers')
    op.drop_table('assignments')
    op.drop_table('class_students')
    op.drop_table('students')
    op.drop_table('classes')
    op.drop_table('users')
