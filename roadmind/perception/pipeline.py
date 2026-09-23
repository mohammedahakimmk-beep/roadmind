"""Perception pipeline + world state. Runs the CV brain on captured frames."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from . import detector, lanes, signs, tracker, vocr


@dataclass
class WorldState:
    ts: float = 0.0
    fps: float = 0.0
    dets: list = field(default_factory=list)
    tracks: list = field(default_factory=list)
    lanes: dict = field(default_factory=lambda: {"valid": False, "offset": 0.0, "angle": 0.0})
    speed_limit: int | None = None
    speed_limit_ts: float = 0.0
    light_state: str = "unknown"
    leader: dict = field(default_factory=dict)   # normalized box of leader vehicle
    leader_distance: float = 0.0                  # 0..1 closeness (h*scale), bigger = closer
    motion: float = 0.0                           # optical-flow px/frame on ground plane
    speed_est: float = 0.0                        # normalized motion->speed hint
    sign_boxes: list = field(default_factory=list)
    thinking: list = field(default_factory=list)

    def has_red_light(self) -> bool:
        return self.light_state == "red"

    def has_stop_sign(self) -> bool:
        for t in self.tracks:
            if t.label == "stop_sign" and t.h > 0.12 and t.y > 0.5:
                return True
        return False


class PerceptionEngine:
    def __init__(self):
        self.det = detector.Detector()
        self.trk = tracker.Tracker()
        self.mem = tracker.Memory()
        self.state = WorldState()
        self.frame = None
        self._prev_gray = None
        self._last_sign_t = 0.0
        self._last_light_t = 0.0
        self._frame_counter = 0
        self._frame_time = []
        self._stop = threading.Event()

    def start(self, capture) -> None:
        self._cap = capture
        if getattr(self, "_thread", None) and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=2.0)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="perceive")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                frame = self._cap.grab()
            except Exception:
                time.sleep(0.05)
                continue
            if frame is None or frame.size == 0:
                time.sleep(0.05)
                continue
            self.frame = frame
            try:
                self._process(frame)
            except Exception:
                pass
            dt = time.perf_counter() - t0
            self._frame_time.append(dt)
            if len(self._frame_time) > 30:
                self._frame_time.pop(0)
            self.state.fps = 1.0 / (sum(self._frame_time) / len(self._frame_time))
            # keep the loop busy: cap near 30fps
            self.state.ts = time.time()

    def _process(self, frame: np.ndarray):
        now = time.time()
        H, W = frame.shape[:2]

        dets = self.det.detect(frame)
        tracks = self.trk.update(dets)
        self.state.dets = dets
        self.state.tracks = tracks

        self.state.lanes = lanes.detect_lanes(frame)

        # motion / speed estimate on ground plane
        self._prev_gray = None if self._prev_gray is None else self._prev_gray
        motion, self._prev_gray = tracker.optical_flow_motion(frame, self._prev_gray)
        self.mem.motion_px.append(motion)
        self.state.motion = round(self.mem.motion(), 3)
        win = list(self.mem.motion_px)
        if len(win) >= 3:
            ref = float(np.percentile(np.asarray(win), 90))
        else:
            ref = 0.05
        self.state.speed_est = round(float(min(1.0, max(0.0, motion / max(1e-3, ref)))), 3)

        # signs + speed limit (throttled, e.g. every ~0.5s)
        if now - self._last_sign_t > 0.5:
            lim, sign_boxes = signs.read_speed_limit(frame)
            self.mem.note_speed_limit(lim)
            self.state.speed_limit = self.mem.speed_limit
            self.state.speed_limit_ts = self.mem.speed_limit_ts
            self.state.sign_boxes = sign_boxes
            self._last_sign_t = now

        # traffic light state
        if now - self._last_light_t > 0.4:
            tl = self._best_track(tracks, "traffic_light", min_h=0.04)
            if tl:
                crop = frame[int((tl.y - tl.h / 2) * H): int((tl.y + tl.h / 2) * H),
                             int((tl.x - tl.w / 2) * W): int((tl.x + tl.w / 2) * W)]
                state = signs.traffic_light_color(crop)
                self.mem.note_light(state)
                self.state.light_state = self.mem.light_state
            self._last_light_t = now

        leader = self.trk.leader()
        if leader:
            self.state.leader = {"x": leader.x, "y": leader.y,
                                 "w": leader.w, "h": leader.h,
                                 "label": leader.label, "id": leader.id}
            self.state.leader_distance = min(1.0, leader.h * 2.2)
        else:
            self.state.leader = {}
            self.state.leader_distance = 0.0

        self._frame_counter += 1

    @staticmethod
    def _best_track(tracks, label, min_h=0.03):
        cands = [t for t in tracks if t.label == label and t.h >= min_h]
        return max(cands, key=lambda t: t.h) if cands else None