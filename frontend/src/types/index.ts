// === Auth ===

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'teacher' | 'school_admin' | 'super_admin';
  avatar_url: string | null;
  subscription_tier: 'free' | 'solo' | 'pro' | 'school';
  preferred_correction_style: CorrectionStyle;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// === Classes & Students ===

export interface Class {
  id: string;
  name: string;
  subject: string | null;
  grade_level: string | null;
  academic_year: string | null;
  is_archived: boolean;
  student_count: number;
  created_at: string;
}

export interface Student {
  id: string;
  full_name: string;
  student_number: string | null;
  parent_email: string | null;
  notes: string | null;
  created_at: string;
}

export interface Assignment {
  id: string;
  class_id: string;
  title: string;
  description: string | null;
  subject: string | null;
  max_score: number | null;
  due_date: string | null;
  answer_key_url: string | null;
  paper_count: number;
  created_at: string;
}

// === Papers & Corrections ===

export type CorrectionStyle = 'red_pen' | 'blue_pen' | 'pencil';

export type ProcessingStatus =
  | 'pending'
  | 'processing'
  | 'reviewed'
  | 'corrected'
  | 'finalized'
  | 'failed';

export type AnnotationType =
  | 'checkmark'
  | 'xmark'
  | 'circle'
  | 'underline'
  | 'strikethrough'
  | 'text_note'
  | 'score_box'
  | 'arrow';

export interface Position {
  x: number; // 0-1 relative to image
  y: number;
}

export interface Bounds {
  width: number;
  height: number;
}

export interface Annotation {
  id: string;
  type: AnnotationType;
  position: Position;
  bounds?: Bounds;
  style: CorrectionStyle;
  text?: string;
  score?: number;
  max_score?: number;
  ai_generated: boolean;
  confidence: number;
  linked_question_id?: string;
  svg_path?: string;
  rotation?: number;
}

export interface QuestionResult {
  number: string;
  question_text: string | null;
  student_answer: string | null;
  correct_answer: string | null;
  is_correct: boolean | null;
  partial_credit: number;
  score: number;
  max_score: number;
  confidence: number;
  answer_region: {
    x_percent: number;
    y_percent: number;
    width_percent: number;
    height_percent: number;
  } | null;
  correction_note: string | null;
}

export interface GradingResult {
  questions: QuestionResult[];
  total_score: number;
  max_score: number;
  overall_feedback: string;
  paper_type: string;
  ocr_confidence: number;
  notes: string;
}

export interface Paper {
  id: string;
  assignment_id: string | null;
  student_id: string | null;
  original_image_url: string;
  processed_image_url: string | null;
  processing_status: ProcessingStatus;
  correction_style: CorrectionStyle;
  annotations: Annotation[] | null;
  evaluation_result: GradingResult | null;
  ai_confidence: number | null;
  total_score: number | null;
  max_score: number | null;
  percentage: number | null;
  grade: string | null;
  corrected_pdf_url: string | null;
  teacher_feedback: string | null;
  created_at: string;
}

// === Dashboard ===

export interface DashboardStats {
  papers_graded_today: number;
  papers_pending: number;
  total_classes: number;
  total_students: number;
  recent_papers: {
    id: string;
    student_id: string | null;
    status: ProcessingStatus;
    score: number | null;
    max_score: number | null;
    created_at: string;
  }[];
}
