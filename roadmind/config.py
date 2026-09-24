"""Config, action whitelist, key bindings, calibration profiles. JSON persisted."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from . import sys_utils

ACTIONS = [
    "throttle", "brake", "steer_left", "steer_right",
    "reverse", "handbrake", "gear_up", "gear_down",
    "blinker_left", "blinker_right", "honk", "abs", "headlights",
]

ACTION_LABELS = {
    "throttle": "Throttle (gas)",
    "brake": "Brake",
    "steer_left": "Steer left",
    "steer_right": "Steer right",
    "reverse": "Reverse",
    "handbrake": "Handbrake",
    "gear_up": "Gear up",
    "gear_down": "Gear down",
    "blinker_left": "Blinker left",
    "blinker_right": "Blinker right",
    "honk": "Honk",
    "abs": "ABS (pulsed braking)",
    "headlights": "Headlights",
}

DEFAULT_BINDINGS = {
    "throttle": "w", "brake": "s", "steer_left": "a", "steer_right": "d",
    "reverse": "1", "handbrake": "space", "gear_up": "e", "gear_down": "q",
    "blinker_left": "left", "blinker_right": "right", "honk": "h",
    "abs": "shift", "headlights": "z",
}

DEFAULT_LIMITS = {"target_speed": 50.0, "max_speed": 200.0, "max_steer": 1.0}

DEFAULT_UI = {
    "show_boxes": True,     # draw bounding boxes on the AI vision overlay
    "show_speed": True,     # draw est. speed labels above cars/humans
    "show_lanes": True,     # draw lane lines + projected path
    "show_hud": True,       # speed-limit dial + thinking ribbon
}


@dataclass
class CalibrationCurve:
    latency_ms: float = 0.0
    response_per_ms: float = 0.0   # normalized response (0..1) gained per ms of hold
    max_hold_ms: float = 300.0


@dataclass
class Profile:
    actions: dict = field(default_factory=lambda: {a: True for a in ACTIONS})
    bindings: dict = field(default_factory=lambda: dict(DEFAULT_BINDINGS))
    limits: dict = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    calibration: dict = field(default_factory=lambda: {a: asdict(CalibrationCurve()) for a in ACTIONS})
    ui: dict = field(default_factory=lambda: dict(DEFAULT_UI))


class RoadMindConfig:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(sys_utils.DATA_DIR, "config.json")
        self.profile = Profile()
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                data = json.load(open(self.path))
                p = Profile()
                if isinstance(data.get("actions"), dict):
                    for a in ACTIONS:
                        p.actions[a] = bool(data["actions"].get(a, True))
                if isinstance(data.get("bindings"), dict):
                    p.bindings.update({k: v for k, v in data["bindings"].items() if k in ACTIONS})
                if isinstance(data.get("limits"), dict):
                    p.limits.update(data["limits"])
                if isinstance(data.get("ui"), dict):
                    p.ui.update({k: v for k, v in data["ui"].items()
                                 if k in DEFAULT_UI})
                if isinstance(data.get("calibration"), dict):
                    for a in ACTIONS:
                        c = data["calibration"].get(a, {})
                        p.calibration[a] = CalibrationCurve(
                            latency_ms=float(c.get("latency_ms", 0.0)),
                            response_per_ms=float(c.get("response_per_ms", 0.0)),
                            max_hold_ms=float(c.get("max_hold_ms", 300.0)),
                        )
                self.profile = p
            except Exception:
                self.profile = Profile()

    def save(self):
        data = {
            "actions": self.profile.actions,
            "bindings": self.profile.bindings,
            "limits": self.profile.limits,
            "ui": self.profile.ui,
            "calibration": {a: asdict(c) if not isinstance(c, dict) else c
                            for a, c in self.profile.calibration.items()},
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def allowed(self, action: str) -> bool:
        return self.profile.actions.get(action, False) and action in self.profile.bindings