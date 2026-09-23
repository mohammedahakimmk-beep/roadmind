"""Safety: global strong-stop, focus watchdog, max-speed clamp."""

from __future__ import annotations

import threading
import time

from . import input_ctl, sys_utils


class Safety:
    def __init__(self):
        self.kill = threading.Event()
        self._pynput = None
        self._hotkey = None

    def start(self, on_kill=None):
        self.kill.clear()
        try:
            from pynput import keyboard

            def _on_trigger():
                self.kill.set()
                input_ctl.release_all()
                if on_kill:
                    on_kill()

            self._hotkey = keyboard.GlobalHotKeys({
                "<ctrl>+<alt>+q": _on_trigger,
            })
            self._hotkey.daemon = True
            self._hotkey.start()
        except Exception:
            import logging
            logging.getLogger("roadmind").warning("global kill hotkey unavailable "
                                                  "(grant Input Monitoring or use the STOP button)")

    def tripped(self) -> bool:
        return self.kill.is_set()

    def stop(self):
        try:
            if self._hotkey:
                self._hotkey.stop()
            if self._pynput:
                pass
        except Exception:
            pass


def game_window_lost_focus(game_owner: str, grace_s: float = 1.5) -> bool:
    if not game_owner:
        return False
    front = sys_utils.frontmost_owner()
    if not front:
        return False
    return front != game_owner