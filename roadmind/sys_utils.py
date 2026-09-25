"""Cross-platform system helpers.

macOS: Quartz/TCC for permissions, window list, Retina scale, app activation.
Windows: win32 APIs for the same - and no permission dance (none required).
"""

from __future__ import annotations

import getpass
import os
import sys

IS_MAC = sys.platform == "darwin"

if IS_MAC:
    APP_SUPPORT = os.path.expanduser("~/Library/Application Support/RoadMind")
else:
    APP_SUPPORT = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "RoadMind")
DATA_DIR = APP_SUPPORT
os.makedirs(DATA_DIR, exist_ok=True)


def _ensure_dpi_aware():
    """Windows only: report real pixels so rects match mss grabs (scale = 1.0)."""
    if IS_MAC:
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def requires_accessibility() -> bool:
    """True when the OS requires an Accessibility-style grant to send keys."""
    return IS_MAC


def is_accessibility_trusted() -> bool:
    """True when this process may post synthetic events (keyboard control).

    Note: AXIsProcessTrusted lives in ApplicationServices/HIServices, not
    Quartz - calling Quartz.AXIsProcessTrusted raises and previously made the
    app *always* report MISSING no matter what the user granted.
    """
    if not IS_MAC:
        return True
    try:
        import ApplicationServices as AS
        if hasattr(AS, "AXIsProcessTrusted"):
            return bool(AS.AXIsProcessTrusted())
    except Exception:
        pass
    try:
        import Quartz
        fn = getattr(Quartz, "CGPreflightPostEventAccess", None)
        if fn:
            return bool(fn())
    except Exception:
        pass
    return False


def input_monitoring_allowed() -> bool:
    """True when this process may observe input (global hotkey)."""
    if not IS_MAC:
        return True
    try:
        import Quartz
        fn = getattr(Quartz, "CGPreflightListenEventAccess", None)
        if fn:
            return bool(fn())
    except Exception:
        pass
    return False


def is_screen_capture_allowed() -> bool:
    if not IS_MAC:
        return True
    try:
        import Quartz
        fn = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
        if fn is None:
            return True
        return bool(fn())
    except Exception:
        return True


def open_settings_pane(suffix: str) -> None:
    """Open the relevant settings pane. macOS: System Settings; Windows: no-op
    (Windows requires no permission grants)."""
    if not IS_MAC:
        return
    try:
        os.system(
            'open "x-apple.systempreferences:com.apple.preference.security?%s"' % suffix)
    except Exception:
        pass


def open_permissions_settings() -> None:
    open_settings_pane("Privacy_ScreenCapture")


def open_accessibility_settings() -> None:
    open_settings_pane("Privacy_Accessibility")


def list_windows(min_w: int = 400, min_h: int = 300, exclude_pid: int | None = None):
    """Return on-screen windows as (name, owner, pid, x, y, w, h) + hwnd (win)."""
    if IS_MAC:
        return _list_windows_mac(min_w, min_h, exclude_pid)
    return _list_windows_win(min_w, min_h, exclude_pid)


def _list_windows_mac(min_w, min_h, exclude_pid):
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
                    "x": int(x), "y": int(y), "w": int(ww), "h": int(hh),
                    "hwnd": None})
    return _dedupe_windows(out)


def _list_windows_win(min_w, min_h, exclude_pid):
    _ensure_dpi_aware()
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    own = exclude_pid or os.getpid()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid = pid.value
        if pid == own:
            return True
        text = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, text, 511)
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < min_w or h < min_h:
            return True
        found.append({
            "name": text.value,
            "owner": _exe_name_for_pid(kernel32, pid),
            "pid": pid,
            "x": int(rect.left), "y": int(rect.top),
            "w": int(w), "h": int(h),
            "hwnd": int(hwnd),
        })
        return True

    user32.EnumWindows(_cb, 0)
    return _dedupe_windows(found)


def _dedupe_windows(out):
    # dedupe by owner+size (games often have unnamed windows)
    seen = set()
    uniq = []
    for w in sorted(out, key=lambda w: -(w["w"] * w["h"])):
        key = (w["owner"], w["w"], w["h"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(w)
    return uniq


def _exe_name_for_pid(kernel32, pid):
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    try:
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def backing_scale() -> float:
    """Points->pixels scale for the main display (1.0 on Windows: we are DPI-aware)."""
    if not IS_MAC:
        _ensure_dpi_aware()
        return 1.0
    try:
        import Quartz
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
    if IS_MAC:
        try:
            import Quartz
            ws = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
            if ws:
                return ws[0].get("kCGWindowOwnerName", "") or ""
        except Exception:
            pass
        return ""
    _ensure_dpi_aware()
    try:
        import ctypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return _exe_name_for_pid(kernel32, pid.value) or ""
    except Exception:
        return ""


def activate_pid(pid: int) -> bool:
    """Bring the given process to the front (used to focus the game before driving)."""
    if IS_MAC:
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
    _ensure_dpi_aware()
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        target = ctypes.c_void_p()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, _lparam):
            pid_ = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_))
            if pid_.value == pid and user32.IsWindowVisible(hwnd):
                target.value = int(hwnd)
                return False  # stop enumerating
            return True

        try:
            user32.EnumWindows(_cb, 0)
        except Exception:
            pass
        if not target.value:
            return False
        user32.SetForegroundWindow(target)
        user32.BringWindowToTop(target)
        return True
    except Exception:
        return False


def is_running_as_root() -> bool:
    if not IS_MAC:
        return False
    return getpass.getuser() == "root"


def is_admin() -> bool:
    """True when this process is elevated (admin). Windows: shell32; macOS: euid."""
    if IS_MAC:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _win_integrity_level(pid):
    """Windows-only: integrity SID's RID (16384=System, 12288=High/admin,
    8192=Medium, 4096=Low). Returns 0 when unknown/unreadable."""
    try:
        import ctypes
        import struct
        from ctypes import wintypes
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        TOKEN_QUERY = 0x0008
        TokenIntegrityLevel = 25
        h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return 0
        try:
            tok = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(h, TOKEN_QUERY, ctypes.byref(tok)):
                return 0
            try:
                buf = ctypes.create_string_buffer(256)
                needed = wintypes.DWORD()
                if not advapi32.GetTokenInformation(tok, TokenIntegrityLevel,
                                                    buf, 256, ctypes.byref(needed)):
                    return 0
                sid_ptr = struct.unpack("P", buf.raw[:ctypes.sizeof(ctypes.c_void_p)])[0]
                if not sid_ptr:
                    return 0
                ln = wintypes.DWORD()
                if not advapi32.GetLengthSid(sid_ptr, ctypes.byref(ln)):
                    return 0
                sidbuf = ctypes.create_string_buffer(ln.value or 68)
                ctypes.memmove(sidbuf, ctypes.c_void_p(sid_ptr), ln.value)
                s = wintypes.LPWSTR()
                if not advapi32.ConvertSidToStringSidW(sidbuf, ctypes.byref(s)) or not s.value:
                    return 0
                last = s.value.rsplit("-", 1)[-1]
                return int(last) if last.isdigit() else 0
            finally:
                advapi32.CloseHandle(tok)
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return 0


def game_elevation_ok(pid: int) -> tuple[bool, str]:
    """Checks the picked game can actually receive keystrokes from us.

    Windows UIPI silently blocks key injection from a normal app into an
    ELEVATED process - the bot watches fine but the car never moves. The fix is
    to run GameROBOT as Administrator too. Always fine on macOS.
    """
    if IS_MAC or not pid:
        return True, ""
    try:
        game_lvl = _win_integrity_level(pid)
        if game_lvl <= 8192 or game_lvl == 0:
            return True, ""
        if is_admin():
            return True, ""
        return (False, "Game runs as Administrator but GameROBOT does not - "
                       "Windows blocks the keystrokes (UIPI), so the bot can "
                       "watch but the car never moves. Close the game, run "
                       "GameROBOT as Administrator, then start the game again.")
    except Exception:
        return True, ""


def native_dialog(title: str, message: str, buttons: tuple = ("OK",),
                  default: str | None = None) -> str | None:
    """Show a NATIVE dialog before any GUI toolkit exists. Returns the pressed
    button label, or None if dismissed. macOS: osascript; Windows: MessageBox."""
    if IS_MAC:
        try:
            import subprocess
            btns = ", ".join(f'"{b}"' for b in buttons)
            dflt = f' default button "{default or buttons[0]}"'
            r = subprocess.run(
                ["osascript", "-e",
                 f'display dialog {message!r} with title {title!r} ' +
                 f'buttons {{{btns}}} {dflt}'],
                capture_output=True, timeout=30)
            out = (r.stdout or b"").decode("utf-8", "ignore")
            for b in buttons:
                if b in out:
                    return b
            return buttons[0] if r.returncode == 0 else None
        except Exception:
            return None
    try:
        import ctypes
        MB_ICONINFORMATION = 0x40
        MB_SYSTEMMODAL = 0x1000
        MB_YESNO = 0x4
        MB_DEFBUTTON2 = 0x100
        flags = MB_ICONINFORMATION | MB_SYSTEMMODAL
        two = len(buttons) == 2
        if two:
            flags |= MB_YESNO
        if default and buttons and default == buttons[-1]:
            flags |= MB_DEFBUTTON2
        r = ctypes.windll.user32.MessageBoxW(0, message, title, flags)
        if two:
            return buttons[0] if r == 6 else buttons[-1]  # IDYES / IDNO
        return buttons[0]
    except Exception:
        return None