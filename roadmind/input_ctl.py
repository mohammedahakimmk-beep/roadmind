"""Keyboard input injection.

macOS:          Quartz CGEvent (needs the Accessibility grant).
Windows:        user32 keybd_event VK codes (needs nothing).

The API is by KEY NAME (w/a/s/d, arrows...) because games re-map controls by
name - the same binding string drives either backend.
"""

from __future__ import annotations

import sys
import threading

IS_MAC = sys.platform == "darwin"

_MAC_KEYCODES = {
    "w": 13, "a": 0, "s": 1, "d": 2,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "space": 49, "shift": 56, "ctrl": 59, "alt": 58, "tab": 48,
    "e": 14, "q": 12, "r": 15, "f": 3, "g": 5, "h": 4, "b": 11,
    "z": 6, "x": 7, "c": 8, "v": 9, "t": 17, "y": 16, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "return": 36, "esc": 53,
}

# Windows virtual-key codes (map.codes shown as 0xVV)
_WIN_KEYCODES = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "space": 0x20, "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "tab": 0x09,
    "e": 0x45, "q": 0x51, "r": 0x52, "f": 0x46, "g": 0x47, "h": 0x48, "b": 0x42,
    "z": 0x5A, "x": 0x58, "c": 0x43, "v": 0x56, "t": 0x54, "y": 0x59, "n": 0x4E, "m": 0x4D,
    "1": 0x31, "2": 0x32, "3": 0x33, "return": 0x0D, "esc": 0x1B,
}

KEYCODES = _MAC_KEYCODES if IS_MAC else _WIN_KEYCODES

_pressed: set[int] = set()
_lock = threading.Lock()


def _post(keycode: int, down: bool):
    if IS_MAC:
        import Quartz
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        return
    import ctypes
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(keycode, 0, 0 if down else KEYEVENTF_KEYUP, 0)


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
    import time
    time.sleep(hold_ms / 1000.0)
    _post(code, False)


def release_all():
    with _lock:
        for code in list(_pressed):
            _post(code, False)
        _pressed.clear()