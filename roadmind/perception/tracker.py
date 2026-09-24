"""Lightweight IoU tracker + memory (speed limit latch, light state, leader, motion).

Also estimates each tracked object's relative approach speed with a simple
projective world model, so the UI can label "CAR · EST 60" above the box.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Projective pinhole-ish model: distance in metres from the object's on-ground
# position. horizon_y is where the road goes to the vanishing point (matched to
# the lane detector's ROI); DIST_K is tuned so a car near the bottom of the
# frame reads ~5-10 m away. Play-pretty estimates, not survey-grade.
HORIZON_Y = 0.42
DIST_K = 6.6


def _to_dist(y_bottom: float) -> float:
    y = max(HORIZON_Y + 0.02, min(0.99, float(y_bottom)))
    return max(1.0, min(80.0, DIST_K / (y - HORIZON_Y)))


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
    hist: deque = field(default_factory=lambda: deque(maxlen=45))
    vx: float = 0.0          # normalized lateral motion / s (smoothed)
    vy: float = 0.0          # normalized vertical motion / s (smoothed)
    speed: float = 0.0       # 0..1 normalized approach speed
    est_kmh: float = 0.0     # est. relative approach speed (play units)
    moving: bool = False     # "fast enough to be a moving object"

    # -- display --
    @property
    def dist(self) -> float:
        """Approx distance (m) of the object ahead of us."""
        return _to_dist(self.y + self.h / 2)

    @property
    def x1(self): return self.x - self.w / 2

    @property
    def x2(self): return self.x + self.w / 2

    @property
    def y1(self): return self.y - self.h / 2

    @property
    def y2(self): return self.y + self.h / 2


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
                best.cls = d["cls"]
                best.label = d["label"]
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
        for t in self.tracks:
            self._estimate_speed(t, now)
        return self.tracks

    # ------------------------------------------------------------------ speeds
    def _estimate_speed(self, t: Track, now: float):
        """Append this frame to the object's history, then estimate approach
        speed from the projective distance change over a ~0.5s window."""
        tb = t.y + t.h / 2                   # on-ground point
        t.hist.append((now, t.x, tb))
        while t.hist and now - t.hist[0][0] > 0.55:
            t.hist.popleft()
        if len(t.hist) < 3:
            return
        t0, x0, y0 = t.hist[0]
        last = t.hist[-1]
        dt = max(1e-3, last[0] - t0)
        # per-second normalized motion (for instabox movement display)
        vx = (last[1] - x0) / dt
        vy = (last[2] - y0) / dt
        t.vx = vx if t.vx == 0 else t.vx * 0.6 + vx * 0.4
        t.vy = vy if t.vy == 0 else t.vy * 0.6 + vy * 0.4
        # projective relative speed
        v = (_to_dist(last[2]) - _to_dist(y0)) / dt * 3.6  # m/s -> km/h
        v = max(-40.0, min(220.0, v))
        t.est_kmh = v * 0.7 + (t.est_kmh if t.est_kmh else v) * 0.3
        t.speed = round(float(min(1.0, max(0.0, abs(t.est_kmh) / 90.0))), 3)
        t.moving = abs(t.est_kmh) > 6.0

    def leader(self) -> Track | None:
        """Closest vehicle ahead: largest box whose bottom is in the lower half
        (i.e. on the road ahead of us), falling back to the largest vehicle."""
        near = [t for t in self.tracks if t.cls in {2, 3, 5, 7} and t.y < 0.8]
        if not near:
            return None
        near.sort(key=lambda t: t.h, reverse=True)
        return near[0]

    def person(self) -> Track | None:
        """Most threatening person on the road ahead (largest, on-ground)."""
        ppl = [t for t in self.tracks if t.cls == 0 and t.y < 0.85]
        if not ppl:
            return None
        return max(ppl, key=lambda t: t.h)

    def stats(self) -> dict:
        """Simple object census: label -> count (useful for the telemetry UI)."""
        out = {}
        for t in self.tracks:
            out[t.label] = out.get(t.label, 0) + 1
        return out


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