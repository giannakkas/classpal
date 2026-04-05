"""
Image preprocessing pipeline for scanned/photographed student papers.

Pipeline:
1. Load image
2. Detect paper edges
3. Perspective correction (4-point transform)
4. Deskew (straighten text lines)
5. Shadow removal + contrast enhancement
6. Noise reduction
7. Output clean, flat image ready for AI analysis
"""

import cv2
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def preprocess_paper(image_bytes: bytes) -> bytes:
    """Full preprocessing pipeline. Returns cleaned JPEG bytes."""
    # Decode
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")

    original_h, original_w = img.shape[:2]
    logger.info(f"Original image: {original_w}x{original_h}")

    # Step 1: Resize if too large (max 3000px on longest edge for processing)
    max_dim = 3000
    scale = 1.0
    if max(original_h, original_w) > max_dim:
        scale = max_dim / max(original_h, original_w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # Step 2: Try to detect and correct perspective
    corrected = try_perspective_correction(img)
    if corrected is not None:
        img = corrected
        logger.info("Perspective correction applied")
    else:
        logger.info("No perspective correction needed or edges not detected")

    # Step 3: Deskew
    img = deskew(img)

    # Step 4: Shadow removal + contrast enhancement
    img = remove_shadows(img)
    img = enhance_contrast(img)

    # Step 5: Denoise (light — preserve handwriting)
    img = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)

    # Step 6: Resize to standard output (max 2000px for AI input)
    h, w = img.shape[:2]
    out_max = 2000
    if max(h, w) > out_max:
        out_scale = out_max / max(h, w)
        img = cv2.resize(img, None, fx=out_scale, fy=out_scale, interpolation=cv2.INTER_AREA)

    # Encode as JPEG
    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buffer.tobytes()


def try_perspective_correction(img: np.ndarray) -> Optional[np.ndarray]:
    """Detect paper edges and apply perspective transform. Uses multiple strategies."""
    result = None
    
    # Strategy 1: Canny edge detection + quadrilateral finding
    result = _detect_quad_canny(img)
    if result is not None:
        logger.info("Auto-crop: Canny quadrilateral detection succeeded")
        return result
    
    # Strategy 2: Adaptive threshold to find white paper region
    result = _detect_quad_threshold(img)
    if result is not None:
        logger.info("Auto-crop: Threshold-based detection succeeded")
        return result
    
    # Strategy 3: Find largest contour bounding box (non-quad fallback)
    result = _detect_bounding_crop(img)
    if result is not None:
        logger.info("Auto-crop: Bounding box crop succeeded")
        return result
    
    logger.info("Auto-crop: No paper detected, using original image")
    return None


def _detect_quad_canny(img: np.ndarray) -> Optional[np.ndarray]:
    """Strategy 1: Canny edges + find quadrilateral contour."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Try multiple Canny thresholds
    for low, high in [(30, 100), (50, 150), (75, 200)]:
        edged = cv2.Canny(blurred, low, high)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged = cv2.dilate(edged, kernel, iterations=3)
        edged = cv2.erode(edged, kernel, iterations=1)
        
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        img_area = img.shape[0] * img.shape[1]
        
        for contour in contours[:5]:
            peri = cv2.arcLength(contour, True)
            # Try different approximation tolerances
            for eps in [0.02, 0.03, 0.05]:
                approx = cv2.approxPolyDP(contour, eps * peri, True)
                if len(approx) == 4:
                    area = cv2.contourArea(approx)
                    if area > img_area * 0.15:  # Lowered from 20% to 15%
                        return four_point_transform(img, approx.reshape(4, 2))
    
    return None


def _detect_quad_threshold(img: np.ndarray) -> Optional[np.ndarray]:
    """Strategy 2: Use adaptive thresholding to find white paper region."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    
    # Threshold to find bright regions (paper is usually white/light)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # Get largest contour
    largest = max(contours, key=cv2.contourArea)
    img_area = img.shape[0] * img.shape[1]
    area = cv2.contourArea(largest)
    
    if area < img_area * 0.15:
        return None
    
    peri = cv2.arcLength(largest, True)
    for eps in [0.02, 0.03, 0.05]:
        approx = cv2.approxPolyDP(largest, eps * peri, True)
        if len(approx) == 4:
            return four_point_transform(img, approx.reshape(4, 2))
    
    return None


def _detect_bounding_crop(img: np.ndarray) -> Optional[np.ndarray]:
    """Strategy 3: Fallback - crop to bounding box of largest contour."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Use Otsu thresholding
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    largest = max(contours, key=cv2.contourArea)
    img_area = img.shape[0] * img.shape[1]
    
    if cv2.contourArea(largest) < img_area * 0.15:
        return None
    
    # Get minimum area rotated rectangle
    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    box = np.int32(box)
    
    # Get the bounding rectangle (axis-aligned)
    x, y, w, h = cv2.boundingRect(largest)
    
    # Add small padding
    pad = 10
    x = max(0, x - pad)
    y = max(0, y - pad)
    w = min(img.shape[1] - x, w + 2 * pad)
    h = min(img.shape[0] - y, h + 2 * pad)
    
    # Only crop if it removes at least 5% of the image
    crop_area = w * h
    if crop_area > img_area * 0.95:
        return None  # Barely any cropping, not worth it
    
    cropped = img[y:y+h, x:x+w]
    logger.info(f"Bounding crop: {img.shape[1]}x{img.shape[0]} -> {w}x{h}")
    return cropped


def four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply perspective transform given 4 corner points."""
    rect = order_points(pts.astype(np.float32))
    (tl, tr, br, bl) = rect

    # Compute width and height of new image
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left has smallest sum
    rect[2] = pts[np.argmax(s)]  # bottom-right has largest sum

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right has smallest difference
    rect[3] = pts[np.argmax(diff)]  # bottom-left has largest difference
    return rect


def deskew(img: np.ndarray) -> np.ndarray:
    """Detect text line angles and rotate to correct skew."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)

    # Threshold to get text regions
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    # Find coordinates of non-zero pixels (text)
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return img

    # Get minimum area bounding box angle
    angle = cv2.minAreaRect(coords)[-1]

    # Adjust angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only correct if skew is small (< 15 degrees)
    if abs(angle) > 15 or abs(angle) < 0.3:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    logger.info(f"Deskewed by {angle:.2f} degrees")
    return rotated


def remove_shadows(img: np.ndarray) -> np.ndarray:
    """Remove shadows using morphological operations."""
    rgb_planes = cv2.split(img)
    result_planes = []

    for plane in rgb_planes:
        # Large kernel dilation to estimate background
        dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        # Subtract background, normalize
        diff = 255 - cv2.absdiff(plane, bg)
        result_planes.append(cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX))

    return cv2.merge(result_planes)


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)

    enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def check_image_quality(image_bytes: bytes) -> dict:
    """Check if image is suitable for processing. Returns quality metrics."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "reason": "Cannot decode image"}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Check resolution
    if min(h, w) < 500:
        return {"ok": False, "reason": "Image too small. Minimum 500px on shortest edge."}

    # Check blur (Laplacian variance)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < 50:
        return {"ok": False, "reason": "Image is too blurry. Hold the camera steady."}

    # Check brightness
    mean_brightness = np.mean(gray)
    if mean_brightness < 40:
        return {"ok": False, "reason": "Image is too dark. Improve lighting."}
    if mean_brightness > 240:
        return {"ok": False, "reason": "Image is overexposed."}

    return {
        "ok": True,
        "width": w,
        "height": h,
        "blur_score": round(float(blur_score), 1),
        "brightness": round(float(mean_brightness), 1),
    }
