"""PWM-style controller: turns continuous Drivetrain targets into timed key holds."""

from __future__ import annotations

import threading
import time

from .. import config as C
from .. import input_ctl


class Controller:
    """Runs a 25 Hz loop; only whitelisted actions ever reach the keyboard."""

    def __init__(self, cfg: "C.RoadMindConfig"):
        self.cfg = cfg
        self.drivetrain = None
        self.armed = False
        self._stop = threading.Event()
        self._pulse = threading.Event()
        self._thread = None
        self._pressed_last = set()
        self._blinker_holds = {}
        self.on_alert = None  # callback(str)

    def set_plan(self, dt):
        self.drivetrain = dt

    def arm(self):
        if self._thread and self._thread.is_alive():
            return
        self.armed = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="control")
        self._thread.start()

    def disarm(self):
        self.armed = False
        self._stop.set()
        input_ctl.release_all()
        self._pressed_last.clear()
        self._blinker_holds.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _allowed(self) -> set[str]:
        return {a for a in C.ACTIONS if self.cfg.allowed(a)}

    def _loop(self):
        last_honk = 0.0
        blink_flip = {}
        while not self._stop.is_set():
            if not self.armed:
                time.sleep(0.01)
                continue
            allowed = self._allowed()
            dt = self.drivetrain
            now = time.time()
            want = set()
            if dt is not None:
                # steering
                if abs(dt.steer) > 0.05:
                    key = "steer_left" if dt.steer < 0 else "steer_right"
                    if key in allowed:
                        want.add(self.cfg.profile.bindings[key])
                # throttle / brake
                if dt.throttle > 0.2 and "throttle" in allowed:
                    want.add(self.cfg.profile.bindings["throttle"])
                if dt.brake > 0.2 and "brake" in allowed:
                    if "abs" in allowed and dt.mode in ("stopped", "hard_follow"):
                        # pulsed braking, always off within 35ms windows
                        if int(now * 1000) % 90 < 45:
                            want.add(self.cfg.profile.bindings["brake"])
                    else:
                        want.add(self.cfg.profile.bindings["brake"])
                # blinkers
                for side, flag in (("blinker_left", dt.blinker_left),
                                   ("blinker_right", dt.blinker_right)):
                    if side in allowed:
                        if flag and side not in blink_flip:
                            input_ctl.tap(self.cfg.profile.bindings[side], hold_ms=90)
                            blink_flip[side] = now + 0.9
                        elif now > blink_flip.get(side, 0):
                            blink_flip.pop(side, None)
                # honk rarity safety
                if dt.honk and "honk" in allowed and now - last_honk > 4.0:
                    input_ctl.tap(self.cfg.profile.bindings["honk"], hold_ms=180)
                    last_honk = now

            # apply/release
            for key in (want - self._pressed_last):
                input_ctl.press(key)
            for key in (self._pressed_last - want):
                input_ctl.release(key)
            self._pressed_last = want
            time.sleep(0.04)