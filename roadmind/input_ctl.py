"""Keyboard input injection via CGEvent. Requires Accessibity permission."""

from __future__ import annotations

import threading
import time

import Quartz

# macOS virtual keycodes for common keys (default bindings; games re-map in settings)
KEYCODES = {
    "w": 13, "a": 0, "s": 1, "d": 2,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "space": 49, "shift": 56, "ctrl": 59, "alt": 58, "tab": 48,
    "e": 14, "q": 12, "r": 15, "f": 3, "g": 5, "h": 4, "b": 11,
    "z": 6, "x": 7, "c": 8, "v": 9, "t": 17, "y": 16, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "return": 36, "esc": 53,
}

_pressed: set[int] = set()
_lock = threading.Lock()


def _post(keycode: int, down: bool):
    ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def press(name: str):
    code = KEYCODES.get(name.lower())
    if code is None:
        return
    with _lock:
        if code in _pressed:
            return
        _post(code, True)
        _pressed.add(code)


def release(name: str):
    code = KEYCODES.get(name.lower())
    if code is None:
        return
    with _lock:
        if code not in _pressed:
            return
        _post(code, False)
        _pressed.discard(code)


def tap(name: str, hold_ms: int = 40):
    code = KEYCODES.get(name.lower())
    if code is None:
        return
    _post(code, True)
    time.sleep(hold_ms / 1000.0)
    _post(code, False)


def release_all():
    with _lock:
        for code in list(_pressed):
            _post(code, False)
        _pressed.clear()