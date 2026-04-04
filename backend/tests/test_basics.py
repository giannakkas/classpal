"""Basic smoke tests for ClassPal backend."""

import pytest
from unittest.mock import patch


def test_config_loads():
    """Verify config loads without errors."""
    from app.core.config import Settings
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        jwt_secret="test-secret-key-minimum-length",
    )
    assert settings.app_name == "ClassPal API"
    assert settings.jwt_algorithm == "HS256"


def test_password_hashing():
    """Verify password hash and verify work."""
    from app.core.auth import hash_password, verify_password
    hashed = hash_password("testpass123")
    assert hashed != "testpass123"
    assert verify_password("testpass123", hashed)
    assert not verify_password("wrongpass", hashed)


def test_jwt_creation():
    """Verify JWT tokens can be created and decoded."""
    from app.core.auth import create_access_token, create_refresh_token, decode_token

    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key-for-testing"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_expire_minutes = 15
        mock_settings.refresh_token_expire_days = 7

        access = create_access_token("user-123", "teacher")
        refresh = create_refresh_token("user-123")

        assert access is not None
        assert refresh is not None

        payload = decode_token(access)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "teacher"
        assert payload["type"] == "access"


def test_image_quality_check():
    """Verify image quality checker handles various inputs."""
    from app.services.image_processing import check_image_quality
    import numpy as np
    import cv2

    # Create a valid test image (white paper with some text-like noise)
    img = np.ones((800, 600, 3), dtype=np.uint8) * 240
    # Add some contrast
    cv2.rectangle(img, (50, 50), (550, 750), (0, 0, 0), 2)
    cv2.putText(img, "Test", (100, 400), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 3)

    _, buffer = cv2.imencode(".jpg", img)
    result = check_image_quality(buffer.tobytes())
    assert result["ok"] is True
    assert result["width"] == 600
    assert result["height"] == 800

    # Test with too-small image
    small = np.ones((100, 100, 3), dtype=np.uint8) * 200
    _, small_buf = cv2.imencode(".jpg", small)
    result = check_image_quality(small_buf.tobytes())
    assert result["ok"] is False
    assert "too small" in result["reason"].lower()


def test_grading_result_to_annotations():
    """Verify grading result converts to annotation objects."""
    from app.services.grading import grading_result_to_annotations

    result = {
        "questions": [
            {
                "number": "1",
                "is_correct": True,
                "confidence": 0.95,
                "answer_region": {
                    "x_percent": 0.3,
                    "y_percent": 0.2,
                    "width_percent": 0.15,
                    "height_percent": 0.03,
                },
                "score": 1,
                "max_score": 1,
                "correction_note": None,
            },
            {
                "number": "2",
                "is_correct": False,
                "confidence": 0.88,
                "answer_region": {
                    "x_percent": 0.3,
                    "y_percent": 0.35,
                    "width_percent": 0.2,
                    "height_percent": 0.03,
                },
                "score": 0,
                "max_score": 1,
                "correction_note": "7 × 8 = 56, not 54",
            },
        ],
        "total_score": 1,
        "max_score": 2,
    }

    annotations = grading_result_to_annotations(result, "red_pen")

    # Should have: checkmark for Q1, xmark + note + underline for Q2, total score box
    types = [a["type"] for a in annotations]
    assert "checkmark" in types
    assert "xmark" in types
    assert "text_note" in types
    assert "underline" in types
    assert "score_box" in types

    # Verify score box
    score_ann = next(a for a in annotations if a["type"] == "score_box")
    assert "1/2" in score_ann["text"]

    # Verify all use red_pen style
    for a in annotations:
        assert a["style"] == "red_pen"


def test_usage_tier_limits():
    """Verify tier limits are correctly defined."""
    from app.core.usage import TIER_LIMITS

    assert TIER_LIMITS["free"] == 20
    assert TIER_LIMITS["solo"] == 100
    assert TIER_LIMITS["pro"] == 500
    assert TIER_LIMITS["school"] == 300
