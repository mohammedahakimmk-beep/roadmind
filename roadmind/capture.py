"""Per-window screen capture via mss, fast enough for real-time CV."""

from __future__ import annotations

import threading
import time

import numpy as np

from . import sys_utils

_mss = None
_lock = threading.Lock()


def _get_mss():
    global _mss
    if _mss is None:
        import mss
        _mss = mss.mss()
    return _mss


class WindowCapture:
    """Grabs a rectangular region of the screen at interactive rates."""

    def __init__(self, rect_points: tuple[int, int, int, int]):
        scale = sys_utils.backing_scale()
        x, y, w, h = rect_points
        self.rect_px = {
            "left": int(x * scale),
            "top": int(y * scale),
            "width": int(w * scale),
            "height": int(h * scale),
        }
        self.size = (int(w * scale), int(h * scale))

    def grab(self) -> np.ndarray:
        s = _get_mss()
        with _lock:
            shot = s.grab(self.rect_px)
        img = np.asarray(shot, dtype=np.uint8)  # BGRA
        return img[:, :, :3].copy()

    def grab_bgra(self) -> np.ndarray:
        s = _get_mss()
        with _lock:
            shot = s.grab(self.rect_px)
        return np.asarray(shot, dtype=np.uint8)


def list_game_windows():
    return sys_utils.list_windows()