"""Planner FSM: turns WorldState into driving actions, respecting the whitelist.

Outputs a Drivetrain message: steer (-1..1), throttle (0..1), brake (0..1),
blinker_left/right, honk, plus a human-readable intent list shown in the UI.
"""

from __future__ import annotations

import time
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
    hazard: bool = False
    mode: str = "idle"
    reason: list = field(default_factory=list)


class Planner:
    def __init__(self, config):
        self.cfg = config
        self._blinker_l = False
        self._blinker_r = False
        self._last_goal = None
        self._throttle = 0.0      # smoothed target throttle (ramps, not snaps)
        self._steer = 0.0         # smoothed steering (avoids jitter)

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
            self._throttle = 0.0
            d.mode = "stopped"
            d.reason.append("red light / stop sign ahead")
        elif "brake" in allowed and ws.light_state == "yellow" \
                and (time.time() - ws.light_ts) < ws.LIGHT_FRESH_S:
            # yellow: ease off, don't slam (no stale-light risk now)
            if ws.speed_est > 0.35:
                self._throttle = max(0.0, self._throttle - 0.25)
                d.brake = 0.3
                d.throttle = self._throttle
                d.mode = "cautious"
                d.reason.append("yellow light \u2014 easing off")
        elif "brake" in allowed and ws.near_person and ws.person_distance > 0.34:
            d.brake = min(1.0, (ws.person_distance - 0.20) * 1.3)
            d.throttle = 0.0
            self._throttle = 0.0
            d.mode = "mindful"
            d.reason.append(f"human on the road ahead {ws.person_distance:.0%}")
        elif "brake" in allowed and ws.leader and ws.leader_distance > 0.55:
            d.brake = min(1.0, (ws.leader_distance - 0.45) * 1.4)
            d.throttle = 0.0
            self._throttle = 0.0
            d.mode = "hard_follow"
            d.reason.append(f"vehicle close ahead ({ws.leader['label']})")
        else:
            # --- steering (lane keep, smoothed) ---
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
            self._steer = self._steer * 0.55 + steer * 0.45
            d.steer = float(np.clip(self._steer, -1.0, 1.0))

            # --- speed / throttle (ramped, so the car feels smooth) ---
            goal = 1.0 if not goal_speed else 0.92
            if "throttle" in allowed and ws.speed_est < 0.65 and goal_speed:
                target = 1.0 if ws.leader_distance < 0.2 else goal
                if ws.near_person and ws.person_distance > 0.15:
                    target = min(target, 0.45)
                self._throttle = min(target, self._throttle + 0.22)
                d.throttle = self._throttle
                d.mode = "cruise" if ws.lanes.get("valid") else "lane_search"
                d.reason.append(f"cruising toward {int(goal_speed)} km/h" +
                                (" (speed limit)" if lim else ""))
                if ws.has_green_light():
                    d.reason.append("green light \u2014 going")
            elif "brake" in allowed and ws.speed_est > 0.97:
                self._throttle = max(0.0, self._throttle - 0.3)
                d.brake = 0.5
                d.mode = "overspeed"
                d.reason.append("at top of measured range, easing off")
            else:
                self._throttle = max(0.0, self._throttle - 0.3)

            if "brake" in allowed and ws.leader and 0.3 < ws.leader_distance <= 0.55:
                d.brake = min(1.0, (ws.leader_distance - 0.25) * 1.2)
                self._throttle *= 0.35
                d.throttle = self._throttle
                d.mode = "follow"
                d.reason.append(f"following {ws.leader['label']} at safe gap")

            if ws.near_person and 0.12 < ws.person_distance <= 0.34 and "brake" in allowed:
                d.brake = max(d.brake, min(0.7, (ws.person_distance - 0.05) * 1.0))
                self._throttle = min(self._throttle, 0.25)
                d.throttle = self._throttle
                d.mode = "mindful"
                d.reason.append("human ahead - cautious speed")

            if d.throttle <= 0.08 and d.brake <= 0.05:
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
        # Hazards: standing on the brakes because someone is right there, or a
        # full stop. Hazards override blinkers while they flash.
        if "hazard" in allowed and d.brake >= 0.5 and (
                (ws.leader and ws.leader_distance > 0.7) or d.mode in ("stopped", "hard_follow")):
            d.hazard = True
            d.reason.append("warning: hazard lights")
        if d.hazard:
            d.blinker_left = d.blinker_right = False

        self._blinker_l, self._blinker_r = d.blinker_left, d.blinker_right
        self._last_goal = goal_speed
        if not d.reason:
            d.reason.append("following your whitelisted controls")
        return d


def _clip(v, lo, hi):
    return max(lo, min(hi, v))