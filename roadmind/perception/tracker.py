"""Lightweight IoU tracker + memory (speed limit latch, light state, leader, motion)."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Track:
    id: int
    cls: int
    label: str
    x: float = 0.0   # normalized center
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    conf: float = 0.0
    age: int = 0
    last_seen: float = 0.0


def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"] - a["w"] / 2, a["y"] - a["h"] / 2
    ax2, ay2 = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    bx1, by1 = b["x"] - b["w"] / 2, b["y"] - b["h"] / 2
    bx2, by2 = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / ua if ua > 0 else 0.0


class Memory:
    """Holds latched scene memory: speed limit, traffic light, goal, speed history."""

    def __init__(self):
        self.speed_limit: int | None = None
        self.speed_limit_ts: float = 0.0
        self.light_state: str = "unknown"
        self.goal: str = "no goal"
        self.speed_history: deque = deque(maxlen=60)
        self.motion_px: deque = deque(maxlen=30)
        self.did_see_limit = False

    def note_speed_limit(self, val: int):
        if val:
            self.speed_limit = val
            self.speed_limit_ts = time.time()
            self.did_see_limit = True

    def note_light(self, state: str):
        if state and state != "unknown":
            self.light_state = state

    def motion(self) -> float:
        if not self.motion_px:
            return 0.0
        return sum(self.motion_px) / len(self.motion_px)


class Tracker:
    def __init__(self, max_age: float = 0.6, iou_thresh: float = 0.25):
        self.tracks: list[Track] = []
        self._next_id = 0
        self.max_age = max_age
        self.iou_thresh = iou_thresh

    def update(self, dets: list[dict]) -> list[Track]:
        now = time.time()
        for t in self.tracks:
            t.age += 1
        for d in dets:
            best, biou = None, 0.0
            for t in self.tracks:
                v = _iou(d, {"x": t.x, "y": t.y, "w": t.w, "h": t.h})
                if v > biou:
                    best, biou = t, v
            if best and biou >= self.iou_thresh:
                best.x, best.y, best.w, best.h = d["x"], d["y"], d["w"], d["h"]
                best.conf = d["conf"]
                best.age = 0
                best.last_seen = now
            else:
                self.tracks.append(Track(id=self._next_id, cls=d["cls"],
                                         label=d["label"], x=d["x"], y=d["y"],
                                         w=d["w"], h=d["h"], conf=d["conf"],
                                         age=0, last_seen=now))
                self._next_id += 1
        self.tracks = [t for t in self.tracks if (now - t.last_seen) < self.max_age]
        return self.tracks

    def leader(self) -> Track | None:
        """Closest vehicle ahead (largest box, below/center of frame)."""
        veh = [t for t in self.tracks if t.cls in {2, 3, 5, 7}]
        if not veh:
            return None
        return min(veh, key=lambda t: t.h if t.y < 0.8 else 1.0)


def optical_flow_motion(frame_bgr: np.ndarray, prev_gray,
                        h_frac=0.55, step=6, max_corners=90) -> tuple[float, np.ndarray]:
    """Return (mean_px_per_frame_vertical, prev_gray). Ground-plane motion estimate."""
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    if prev_gray is None or prev_gray.shape != gray.shape:
        return 0.0, gray
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=max_corners,
                                  qualityLevel=0.02, minDistance=9)
    if pts is None:
        return 0.0, gray
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None)
    if nxt is None or st is None:
        return 0.0, gray
    good = nxt[st.ravel() == 1]
    if len(good) == 0:
        return 0.0, gray
    return float(np.mean(good[:, 1] - pts[st.ravel() == 1, 1])), gray