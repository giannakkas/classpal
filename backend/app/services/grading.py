"""
AI Grading Service — Uses Claude Vision to read and evaluate student papers.

Single VLM call approach:
1. Send cleaned paper image + optional answer key to Claude Vision
2. Get back structured JSON with questions, answers, scores, and bounding boxes
3. Convert to annotation objects for the correction canvas
"""

import anthropic
import json
import base64
import logging
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = None

def get_anthropic_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client

GRADING_SYSTEM_PROMPT = """You are ClassPal's AI grading engine. You analyze photographs of student papers — typically printed worksheets with handwritten student answers.

CRITICAL LANGUAGE RULE: Detect the language of the paper. ALL text fields in your response (question_text, correct_answer, correction_note, overall_feedback, notes) MUST be written in THE SAME LANGUAGE as the paper. If the paper is in Greek, respond in Greek. If in French, respond in French. Only the JSON keys remain in English.

Your job is to:
1. Detect the language of the paper
2. Read and understand the questions on the paper
3. Read the student's handwritten answers carefully (even if messy)
4. Evaluate each answer for correctness based on the subject and grade level
5. Assign fair scores with partial credit where deserved
6. Provide helpful correction notes IN THE PAPER'S LANGUAGE

You MUST respond with valid JSON only. No markdown, no explanation outside JSON.

Response format:
{
  "language": "el" (ISO 639-1 code of the paper's language),
  "questions": [
    {
      "number": "1",
      "question_text": "Brief description of what was asked (in paper's language)",
      "student_answer": "What the student wrote (in original script/language)",
      "correct_answer": "The correct answer (in paper's language)",
      "is_correct": true/false/null,
      "partial_credit": 0.0 to 1.0,
      "score": 0,
      "max_score": 1,
      "confidence": 0.0 to 1.0,
      "answer_region": {
        "x_percent": 0.0 to 1.0,
        "y_percent": 0.0 to 1.0,
        "width_percent": 0.0 to 1.0,
        "height_percent": 0.0 to 1.0
      },
      "correction_note": "Brief correction note in the paper's language, null if correct"
    }
  ],
  "total_score": 7,
  "max_score": 10,
  "overall_feedback": "Brief overall feedback for the student (in paper's language)",
  "paper_type": "math_worksheet|spelling_test|fill_in_blank|multiple_choice|short_answer|mixed|grammar|essay|unknown",
  "ocr_confidence": 0.0 to 1.0,
  "notes": "Any observations about readability, missing answers, etc. (in paper's language)"
}

Rules:
- ALWAYS write correction_note, correct_answer, overall_feedback, and notes in the SAME LANGUAGE as the paper.
- Read handwriting carefully, especially for non-Latin scripts (Greek, Arabic, Cyrillic, etc.).
- If unsure about a character, consider the context (word, sentence) to determine the most likely reading.
- answer_region coordinates are percentages (0-1) relative to the full image dimensions.
- For partial credit: 0.0 = completely wrong, 0.5 = partially correct, 1.0 = fully correct.
- score = max_score * partial_credit (round to nearest 0.5).
- If you cannot read an answer, set student_answer to "[δυσανάγνωστο]" (or equivalent in the paper's language), is_correct to null, confidence to 0, score to 0.
- Be generous with minor spelling variations on non-spelling tests.
- For language/grammar tests: be strict on spelling, accents, and grammar — these ARE the subject being tested.
- For math: check the work shown, not just the final answer. Give partial credit for correct method with arithmetic error.
- Always provide a correction_note for wrong answers explaining the correct solution briefly.
- Consider the student's grade level when evaluating — a 6th grader's answer should be graded differently than a university student's.
- For Greek papers: pay attention to accents (τόνοι), breathing marks, and proper word formation.
"""

GRADING_WITH_KEY_PROMPT = """Additionally, here is the answer key provided by the teacher. Use this as the authoritative source for correct answers:

{answer_key_text}

Match student answers against this key. If the key provides point values, use those for max_score per question."""


async def grade_paper(
    image_bytes: bytes,
    answer_key_data: Optional[dict] = None,
    answer_key_image_bytes: Optional[bytes] = None,
) -> dict:
    """
    Grade a student paper using Claude Vision.
    
    Args:
        image_bytes: The preprocessed paper image (JPEG)
        answer_key_data: Parsed answer key structure (if previously parsed)
        answer_key_image_bytes: Answer key image (if teacher uploaded an image)
    
    Returns:
        Parsed grading result dict
    """
    # Build the message content
    content = []

    # Add the student paper image
    paper_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    content.append({
        "type": "text",
        "text": "Here is the student's paper to grade:",
    })
    content.append({
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": paper_b64,
        },
    })

    # Add answer key context if available
    if answer_key_image_bytes:
        key_b64 = base64.standard_b64encode(answer_key_image_bytes).decode("utf-8")
        content.append({
            "type": "text",
            "text": "Here is the teacher's answer key:",
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": key_b64,
            },
        })
        content.append({
            "type": "text",
            "text": "Grade the student paper using this answer key as the authoritative source for correct answers.",
        })
    elif answer_key_data:
        key_text = json.dumps(answer_key_data, indent=2)
        content.append({
            "type": "text",
            "text": GRADING_WITH_KEY_PROMPT.format(answer_key_text=key_text),
        })
    else:
        content.append({
            "type": "text",
            "text": "No answer key was provided. Grade based on your knowledge of the subject. Set confidence lower for answers you're less sure about.",
        })

    content.append({
        "type": "text",
        "text": "Analyze and grade this paper now. Respond with JSON only.",
    })

    logger.info("Sending paper to Claude Vision for grading...")

    try:
        response = get_anthropic_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=GRADING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        # Extract text response
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        # Parse JSON (strip markdown fences if present)
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1]  # Remove first line
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

        result = json.loads(clean_text)

        # Log usage
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        logger.info(
            f"Grading complete: {len(result.get('questions', []))} questions found. "
            f"Tokens: {input_tokens} in / {output_tokens} out"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        logger.error(f"Raw response: {response_text[:500]}")
        return {
            "error": "Failed to parse AI response",
            "raw_response": response_text[:1000],
            "questions": [],
            "total_score": 0,
            "max_score": 0,
        }
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        raise


def grading_result_to_annotations(result: dict, correction_style: str = "red_pen") -> list[dict]:
    """Convert AI grading result to annotation objects for the canvas."""
    annotations = []
    
    for q in result.get("questions", []):
        region = q.get("answer_region", {})
        x = region.get("x_percent", 0)
        y = region.get("y_percent", 0)

        if q.get("is_correct") is True:
            # Add checkmark
            annotations.append({
                "id": f"ai-check-{q['number']}",
                "type": "checkmark",
                "position": {"x": x + region.get("width_percent", 0.05) + 0.01, "y": y},
                "style": correction_style,
                "ai_generated": True,
                "confidence": q.get("confidence", 0),
                "linked_question_id": q["number"],
                "score": q.get("score"),
                "max_score": q.get("max_score"),
            })
        elif q.get("is_correct") is False:
            # Add X mark
            annotations.append({
                "id": f"ai-xmark-{q['number']}",
                "type": "xmark",
                "position": {"x": x + region.get("width_percent", 0.05) + 0.01, "y": y},
                "style": correction_style,
                "ai_generated": True,
                "confidence": q.get("confidence", 0),
                "linked_question_id": q["number"],
                "score": q.get("score"),
                "max_score": q.get("max_score"),
            })

            # Add correction note if present
            if q.get("correction_note"):
                annotations.append({
                    "id": f"ai-note-{q['number']}",
                    "type": "text_note",
                    "position": {"x": 0.75, "y": y},  # Right margin
                    "text": q["correction_note"],
                    "style": correction_style,
                    "ai_generated": True,
                    "confidence": q.get("confidence", 0),
                    "linked_question_id": q["number"],
                })

            # Underline the wrong answer
            if region:
                annotations.append({
                    "id": f"ai-underline-{q['number']}",
                    "type": "underline",
                    "position": {"x": x, "y": y + region.get("height_percent", 0.02)},
                    "bounds": {
                        "width": region.get("width_percent", 0.1),
                        "height": 0,
                    },
                    "style": correction_style,
                    "ai_generated": True,
                    "confidence": q.get("confidence", 0),
                    "linked_question_id": q["number"],
                })

    # Add total score box
    if result.get("total_score") is not None:
        annotations.append({
            "id": "ai-score-total",
            "type": "score_box",
            "position": {"x": 0.75, "y": 0.05},  # Top-right area
            "score": result["total_score"],
            "max_score": result.get("max_score", 0),
            "style": correction_style,
            "ai_generated": True,
            "confidence": 1.0,
            "text": f"{result['total_score']}/{result.get('max_score', '?')}",
        })

    return annotations
