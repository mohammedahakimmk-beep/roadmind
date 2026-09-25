"""Object detection via Ultralytics YOLO, run on Metal (MPS) when available."""

from __future__ import annotations

import os
import sys
import threading
import time

import numpy as np

from .. import sys_utils

# COCO class names we care about
CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    9: "traffic_light",
    11: "stop_sign",
}

VEHICLE_CLASSES = {2, 3, 5, 7}

# YOLO11 size toggle: "n" is bundled with the EXE; "s"/"m" auto-download on
# first use (saved under the writable data dir, ~19 MB / ~49 MB weights).
MODEL_SIZES = {
    "n": "yolo11n.pt",
    "s": "yolo11s.pt",
    "m": "yolo11m.pt",
}


def resolve_model_path(model_name: str = "yolo11n.pt") -> str:
    """Locate the weights file: bundled resource -> data dir -> download target."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        bundled = os.path.join(base, model_name)
        if os.path.exists(bundled):
            return bundled
    local = os.path.join(sys_utils.DATA_DIR, model_name)
    if os.path.exists(local):
        return local
    if os.path.exists(model_name):
        return model_name
    return local  # ultralytics will download here (writable, offline-safe)


class Detector:
    def __init__(self, model_name: str = "yolo11n.pt", conf: float = 0.35, imgsz: int = 640):
        self.model = None
        self.model_name = model_name
        self.path = resolve_model_path(model_name)
        self.conf = conf
        self.imgsz = imgsz
        self.device = "cpu"
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            from ultralytics import YOLO
            import torch
            # Windows torch has no 'mps' attribute; guard so CPU still loads
            mps = getattr(getattr(torch, "backends", None), "mps", None)
            if mps is not None and mps.is_available():
                self.device = "mps"
            self.model = YOLO(self.path)
            if self.device == "mps":
                self.model.to("mps")
        except Exception:
            self.model = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def detect(self, frame_bgr: np.ndarray) -> list[dict]:
        """Return list of {x,y,w,h,cls,conf,label,is_vehicle} in frame pixel coords."""
        if self.model is None:
            return []
        H, W = frame_bgr.shape[:2]
        try:
            with self._lock:
                r = self.model.predict(frame_bgr, imgsz=self.imgsz, conf=self.conf,
                                       verbose=False, device=self.device)
            dets = []
            if r and r[0].boxes is not None:
                for box in r[0].boxes:
                    cid = int(box.cls[0].item())
                    if cid not in CLASSES:
                        continue
                    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                    dets.append({
                        "x": x1 / W, "y": y1 / H,
                        "w": (x2 - x1) / W, "h": (y2 - y1) / H,
                        "cls": cid, "label": CLASSES[cid],
                        "conf": float(box.conf[0].item()),
                        "is_vehicle": cid in VEHICLE_CLASSES,
                    })
            return dets
        except Exception:
            return []