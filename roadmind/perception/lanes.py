"""Lane detection: bottom-ROI edge + Hough, cluster into left/right lane lines."""

from __future__ import annotations

import numpy as np


def detect_lanes(img_bgr: np.ndarray) -> dict:
    """Return dict with left/right lane line info relative to center.

    out: {
      'valid': bool,
      'offset': float,      # +1..-1 lateral offset, negative = shifted right
      'angle': float,       # combined road angle (-1 left .. +1 right)
      'center_line': (slope, intercept) in normalized coords or None
    }
    """
    import cv2

    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    roi = gray[int(h * 0.55):, :]
    roi = cv2.GaussianBlur(roi, (5, 5), 0)
    edges = cv2.Canny(roi, 70, 160)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=44,
                            minLineLength=int(h * 0.10), maxLineGap=14)
    if lines is None or len(lines) == 0:
        return {"valid": False, "offset": 0.0, "angle": 0.0, "center_line": None}

    left_xs, right_xs = [], []
    slope_acc = 0.0
    n = 0
    for line in lines:
        pts = line[0] if line.ndim == 2 else line
        x1, y1, x2, y2 = pts
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 4:
            continue
        m = dy / dx  # negative for right-leaning (vertical-ish) lines in image coords
        if abs(m) > 0.55:  # vertical-ish lines only
            midx = (x1 + x2) / 2.0
            if m < 0:
                left_xs.append(midx)
            else:
                right_xs.append(midx)
            slope_acc += m
            n += 1

    offset = 0.0
    if n:
        slope_acc /= n
    if left_xs and right_xs:
        lc = np.median(left_xs) / w
        rc = np.median(right_xs) / w
        center = 0.5 * (lc + rc)
        offset = (center - 0.5) * 2.0  # -1..1
    elif left_xs:
        lc = np.median(left_xs) / w
        offset = max(-1.0, (lc - 0.45) * 3.0)
    elif right_xs:
        rc = np.median(right_xs) / w
        offset = min(1.0, (rc - 0.55) * 3.0)

    angle = float(np.clip(slope_acc * 1.4, -1.0, 1.0))
    if left_xs or right_xs:
        return {"valid": True, "offset": float(np.clip(offset, -1, 1)), "angle": angle,
                "center_line": True}
    return {"valid": False, "offset": 0.0, "angle": angle, "center_line": None}