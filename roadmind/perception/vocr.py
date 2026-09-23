"""Apple Vision OCR (native, very fast on Apple Silicon) for sign + HUD text."""

from __future__ import annotations

import time

import numpy as np


def _to_cgimage(png_bytes):
    import Quartz
    import Vision
    data = Foundation.NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    if not src:
        return None
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _to_cgimage_np(img_bgr: np.ndarray) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".png", img_bgr)
    return buf.tobytes()


_cache = {}


def ocr_region(img_bgr: np.ndarray) -> list[str]:
    """OCR a numpy BGR image crop, return recognized strings (top-candidates)."""
    try:
        global Foundation
        import Foundation
        import Vision
    except Exception:
        return []
    try:
        png = _to_cgimage_np(img_bgr)
        key = (hash(png[:1024]), len(png))
        now = time.time()
        _cache.pop(key, None)  # keep small
        im = _to_cgimage(png)
        if im is None:
            return []
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(im, {})
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
        req.setUsesLanguageCorrection_(False)
        handler.performRequests_error_([req], None)
        texts = []
        for obs in req.results() or []:
            texts.append(obs.topCandidates_(1)[0].string())
        return texts
    except Exception:
        return []


def ocr_speed_crop(img_bgr: np.ndarray) -> float | None:
    """Try to parse a speed (number) from an OCR crop. Returns km/h value or None."""
    texts = ocr_region(img_bgr)
    for t in texts or []:
        s = t.strip().replace(",", ".")
        digits = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        if not digits:
            continue
        try:
            v = float(digits.split(".")[0])
        except Exception:
            continue
        if 3 <= v <= 400:
            return v
    return None