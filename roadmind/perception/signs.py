"""Traffic sign reading: red-circle speed-limit signs via segmentation + native OCR."""

from __future__ import annotations

import numpy as np
import cv2

from . import vocr


def find_red_circles(img_bgr: np.ndarray, max_n: int = 3) -> list[dict]:
    import cv2

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, (0, 70, 50), (12, 255, 255))
    m2 = cv2.inRange(hsv, (168, 70, 50), (180, 255, 255))
    mask = cv2.bitwise_or(m1, m2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    H, W = img_bgr.shape[:2]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:max_n]:
        area = cv2.contourArea(c)
        if area < (W * H * 0.0006):   # tiny -> ignore
            continue
        (cx, cy), r = cv2.minEnclosingCircle(c)
        circ = 4 * np.pi * area / max(1.0, cv2.arcLength(c, True) ** 2)
        if circ < 0.45:               # not circle-ish
            continue
        x, y, w, h = int(cx - r), int(cy - r), int(r * 2), int(r * 2)
        out.append({"x": max(0, x), "y": max(0, y), "w": w, "h": h,
                    "cx": cx / W, "cy": cy / H})
    return out


def read_speed_limit(img_bgr: np.ndarray) -> tuple[int | None, list[dict]]:
    """Detect speed-limit-style circular signs and OCR their value."""
    best = None
    with_text = []
    for c in find_red_circles(img_bgr):
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        pad = 6
        crop = img_bgr[max(0, y - pad): y + h + pad, max(0, x - pad): x + w + pad]
        if crop.size == 0:
            continue
        up = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        texts = vocr.ocr_region(up)
        for t in texts or []:
            digit = "".join(ch for ch in t if ch.isdigit())
            if digit.isdigit() and 1 <= int(digit) <= 200:
                val = int(digit)
                if len(digit) >= 2:
                    best = val
                c["text"] = digit
                with_text.append(c)
    return best, with_text


def traffic_light_color(crop_bgr: np.ndarray) -> str:
    """Return 'red' | 'yellow' | 'green' | 'unknown' from a traffic-light crop."""
    import cv2
    if crop is None or crop.size == 0:
        return "unknown"
    try:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    except Exception:
        return "unknown"
    score = {}
    score["green"] = int(cv2.inRange(hsv, (50, 70, 70), (90, 255, 255)).sum())
    score["yellow"] = int(cv2.inRange(hsv, (18, 90, 90), (40, 255, 255)).sum())
    score["red"] = int(cv2.inRange(hsv, (0, 70, 70), (12, 255, 255)).sum()) + \
                   int(cv2.inRange(hsv, (168, 70, 70), (180, 255, 255)).sum())
    if max(score.values()) < 40:
        return "unknown"
    return max(score, key=score.get)