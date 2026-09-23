"""macOS system helpers: permissions, windows, Retina scale."""

from __future__ import annotations

import getpass
import os

APP_SUPPORT = os.path.expanduser(f"~/Library/Application Support/RoadMind")
DATA_DIR = APP_SUPPORT
os.makedirs(DATA_DIR, exist_ok=True)


def is_accessibility_trusted() -> bool:
    try:
        import Quartz
        return bool(Quartz.AXIsProcessTrusted())
    except Exception:
        return False


def is_screen_capture_allowed() -> bool:
    try:
        import Quartz
        fn = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
        if fn is None:
            return True
        return bool(fn())
    except Exception:
        return True


def open_permissions_settings() -> None:
    """Open the System Settings pane for the given permission."""
    try:
        os.system(
            'open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"'
        )
    except Exception:
        pass


def open_accessibility_settings() -> None:
    try:
        os.system(
            'open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"'
        )
    except Exception:
        pass


def list_windows(min_w: int = 400, min_h: int = 300, exclude_pid: int | None = None):
    """Return on-screen windows as (name, owner, pid, x, y, w, h) in points."""
    import Quartz

    own = exclude_pid or os.getpid()
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
    out = []
    for w in wins:
        if w.get("kCGWindowLayer", 0) != 0:
            continue
        pid = w.get("kCGWindowOwnerPID", -1)
        if pid == own:
            continue
        name = w.get("kCGWindowName", "") or ""
        owner = w.get("kCGWindowOwnerName", "") or ""
        b = w.get("kCGWindowBounds") or {}
        x, y, ww, hh = b.get("X", 0), b.get("Y", 0), b.get("Width", 0), b.get("Height", 0)
        if ww < min_w or hh < min_h:
            continue
        out.append({"name": name, "owner": owner, "pid": pid,
                    "x": int(x), "y": int(y), "w": int(ww), "h": int(hh)})
    # dedupe by owner+size (games often have unnamed windows)
    seen = set()
    uniq = []
    for w in out:
        key = (w["owner"], w["w"], w["h"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(w)
    return sorted(uniq, key=lambda w: -(w["w"] * w["h"]))


def backing_scale() -> float:
    """Compute points->pixels scale for the main display."""
    try:
        import Quartz
        # Quartz bounds are in points
        disp = Quartz.CGMainDisplayID()
        rect = Quartz.CGDisplayBounds(disp)
        points_w = rect.size.width
        import mss
        with mss.mss() as s:
            px_w = s.monitors[0]["width"]
        scale = px_w / points_w
        return scale if scale > 0 else 2.0
    except Exception:
        return 2.0


def frontmost_owner() -> str:
    try:
        import Quartz
        ws = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
        if ws:
            return ws[0].get("kCGWindowOwnerName", "") or ""
    except Exception:
        pass
    return ""


def activate_pid(pid: int) -> bool:
    """Bring the given process to the front (used to focus the game before driving)."""
    try:
        from AppKit import (NSRunningApplication,
                            NSApplicationActivateAllWindows,
                            NSApplicationActivateIgnoringOtherApps)
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app:
            app.activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps | NSApplicationActivateAllWindows)
            return True
    except Exception:
        pass
    return False


def is_running_as_root() -> bool:
    return getpass.getuser() == "root"