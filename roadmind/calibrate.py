"""Fully-automatic calibration probe.

Holds each whitelisted action key for a few seconds while the game is focused,
measures the response (optical-flow motion / lane shift) and stores latency +
gain + max hold into the active profile. Requires the car to be somewhere safe
(a parked area / test section) and the game window focused.

Flow-based calibration works in ANY game with a road — no HUD knowledge needed.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from . import config as C
from . import input_ctl

PROBE_HOLD_S = 1.6
BASELINE_S = 0.7
STEPS = ["throttle", "brake", "steer_left", "steer_right"]


class CalibrationWizard:
    def __init__(self, cfg: C.RoadMindConfig, capture, on_step=None, on_done=None,
                 on_error=None, on_progress=None):
        self.cfg = cfg
        self.cap = capture
        self.on_step = on_step
        self.on_done = on_done
        self.on_error = on_error
        self.on_progress = on_progress
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()
        input_ctl.release_all()

    def _flow(self) -> float:
        try:
            f1 = self.cap.grab()
            time.sleep(0.05)
            f2 = self.cap.grab()
            import cv2
            g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
            if g1.shape != g2.shape:
                return 0.0
            flow = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            return float(np.mean(mag))
        except Exception:
            return 0.0

    def run(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        try:
            steps = [a for a in STEPS if self.cfg.allowed(a)]
            if not steps:
                if self.on_error:
                    self.on_error("enable throttle/brake/steering in the whitelist first")
                return
            results = {}
            for i, action in enumerate(steps):
                if self._stop.is_set():
                    break
                if self.on_progress:
                    self.on_progress((i + 1) / (len(steps) + 2))
                if self.on_step:
                    self.on_step(action, f"Probing {C.ACTION_LABELS[action]} "
                                         f"(key '{self.cfg.profile.bindings.get(action)}')")
                time.sleep(0.4)
                base = self._flow()
                key = self.cfg.profile.bindings.get(action)
                if not key:
                    continue
                t0 = time.perf_counter()
                input_ctl.press(key)
                resp = 0.0
                latency = 0.0
                samples = []
                while time.perf_counter() - t0 < PROBE_HOLD_S:
                    if self._stop.is_set():
                        break
                    v = self._flow()
                    samples.append(v)
                    if resp == 0.0 and v > base * 1.15 + 0.03:
                        resp = 1.0
                        latency = (time.perf_counter() - t0) * 1000.0
                    time.sleep(0.03)
                input_ctl.release(key)
                gain = float(max(samples) - base) if samples else 0.0
                results[action] = C.CalibrationCurve(
                    latency_ms=round(latency, 1),
                    response_per_ms=round(gain / max(1.0, PROBE_HOLD_S * 1000.0), 5),
                    max_hold_ms=PROBE_HOLD_S * 1000.0,
                )
            if results:
                for a, curve in results.items():
                    self.cfg.profile.calibration[a] = curve
                self.cfg.save()
            if self.on_progress:
                self.on_progress(1.0)
            if self.on_done:
                self.on_done(results)
        except Exception as e:
            input_ctl.release_all()
            if self.on_error:
                self.on_error(str(e))