"""Planner FSM: turns WorldState into driving actions, respecting the whitelist.

Outputs a Drivetrain message: steer (-1..1), throttle (0..1), brake (0..1),
blinker_left/right, honk, plus a human-readable intent list shown in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Drivetrain:
    steer: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    blinker_left: bool = False
    blinker_right: bool = False
    honk: bool = False
    headlights: bool = False
    mode: str = "idle"
    reason: list = field(default_factory=list)


class Planner:
    def __init__(self, config):
        self.cfg = config
        self._blinker_l = False
        self._blinker_r = False
        self._last_goal = None

    def plan(self, ws, allowed: set[str]) -> Drivetrain:
        d = Drivetrain()
        if not ws:
            d.mode = "waiting"
            d.reason = ["no perception yet"]
            return d

        lim = ws.speed_limit
        goal_speed = ws.speed_limit if lim else self.cfg.profile.limits["target_speed"]

        # --- STOP conditions first ---
        if "brake" in allowed and (ws.has_red_light() or ws.has_stop_sign()):
            d.brake = 1.0
            d.throttle = 0.0
            d.mode = "stopped"
            d.reason.append("red light / stop sign ahead")
        elif "brake" in allowed and ws.leader and ws.leader_distance > 0.55:
            d.brake = min(1.0, (ws.leader_distance - 0.45) * 1.4)
            d.throttle = 0.0
            d.mode = "hard_follow"
            d.reason.append(f"vehicle close ahead ({ws.leader['label']})")
        else:
            # --- steering (lane keep) ---
            steer = 0.0
            if "steer_left" in allowed or "steer_right" in allowed:
                offset = ws.lanes.get("offset", 0.0)
                angle = ws.lanes.get("angle", 0.0)
                if ws.lanes.get("valid"):
                    steer = float(np.clip(-offset * 1.6 + angle * 0.4, -1.0, 1.0))
                elif ws.leader:
                    dx = ws.leader["x"] - 0.5
                    steer = float(np.clip(-dx * 2.0, -1.0, 1.0))
                if steer < 0 and "steer_left" not in allowed:
                    steer = 0.0
                if steer > 0 and "steer_right" not in allowed:
                    steer = 0.0
            d.steer = steer

            # --- speed / throttle ---
            if "throttle" in allowed and ws.speed_est < 0.65 and goal_speed:
                d.throttle = min(1.0, 0.85 if ws.leader_distance < 0.2 else 1.0)
                d.mode = "cruise" if ws.lanes.get("valid") else "lane_search"
                d.reason.append(f"cruising toward {int(goal_speed)} km/h" +
                                (" (speed limit)" if lim else ""))
            elif "brake" in allowed and ws.speed_est > 0.97:
                d.brake = 0.5
                d.mode = "overspeed"
                d.reason.append("at top of measured range, easing off")

            if "brake" in allowed and ws.leader and 0.3 < ws.leader_distance <= 0.55:
                d.brake = min(1.0, (ws.leader_distance - 0.25) * 1.2)
                d.throttle *= 0.35
                d.mode = "follow"
                d.reason.append(f"following {ws.leader['label']} at safe gap")

            if d.throttle <= 0.05 and d.brake <= 0.05:
                d.mode = "coasting"

        # --- signals + honk ---
        if "blinker_left" in allowed and d.steer < -0.35:
            d.blinker_left = True
        elif "blinker_right" in allowed and d.steer > 0.35:
            d.blinker_right = True
        if "honk" in allowed and "brake" in allowed and ws.leader and ws.leader_distance > 0.7:
            d.honk = True
            d.reason.append("warning: vehicle very close")
        if "headlights" in allowed:
            d.headlights = self.cfg.profile.actions.get("headlights", True)

        self._blinker_l, self._blinker_r = d.blinker_left, d.blinker_right
        self._last_goal = goal_speed
        if not d.reason:
            d.reason.append("following your whitelisted controls")
        return d


def _clip(v, lo, hi):
    return max(lo, min(hi, v))