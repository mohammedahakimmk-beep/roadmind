"""Application entry point.

Every route is wrapped so the app NEVER dies invisibly: on any error it writes
a crash log to ~/Library/Application Support/RoadMind/crash.log and shows a
native dialog (the bundled .app has no console, so naked exceptions look like
silent crashes).
"""

from __future__ import annotations

import sys
import time
import traceback

# Windows: become per-monitor DPI aware BEFORE Tk creates any window, so window
# rects (GetWindowRect) and screen grabs (mss) both run in PHYSICAL pixels.
# Otherwise a 150%-scaled display renames regions and the capture misses the
# picked window (or grabs the wrong swath of screen).
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _write_crash(exc: BaseException) -> str | None:
    from roadmind import sys_utils
    try:
        path = sys_utils.DATA_DIR + "/crash.log"
        with open(path, "a") as f:
            f.write("\n===== %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("%r\n" % exc)
            f.write(traceback.format_exc())
        return path
    except Exception:
        return None


def _show_crash_dialog(exc: BaseException, log_path: str | None) -> None:
    """Visible error instead of a silent quit. Fails safe."""
    try:
        from roadmind import sys_utils
        msg = (f"GameROBOT hit an error:\n\n{exc}\n\n"
               "A crash log was saved to:\n" + (log_path or sys_utils.DATA_DIR + "/crash.log") +
               "\nShare it with the project to get it fixed.")
        sys_utils.native_dialog("GameROBOT error", msg, buttons=("OK",))
    except Exception:
        pass


def safe(main_fn):
    def _wrapper() -> int:
        try:
            return main_fn()
        except BaseException as exc:  # noqa: BLE001 - crash-proofing is the point
            log = _write_crash(exc)
            _show_crash_dialog(exc, log)
            return 2
    return _wrapper


@safe
def run() -> int:
    from roadmind.ui.main_window import build_app
    app, _ = build_app()
    return app.mainloop()


@safe
def doctor() -> int:
    from roadmind import sys_utils
    import platform
    print(f"GameROBOT doctor ({platform.system()})")
    if sys_utils.IS_MAC:
        print(f"  Accessibility   : {'GRANTED' if sys_utils.is_accessibility_trusted() else 'MISSING'}")
        print(f"  Screen capture  : {'GRANTED' if sys_utils.is_screen_capture_allowed() else 'MISSING'}")
        im = "GRANTED" if sys_utils.input_monitoring_allowed() else "optional (needed for ctrl+alt+Q hotkey)"
        print(f"  Input monitoring: {im}")
    else:
        print("  Permissions     : none required on Windows")
    print("  Windows found  :", len(sys_utils.list_windows(min_w=200, min_h=200)))
    print("  Updates        : auto-checked at startup (GitHub manifest), silent on failure")
    return 0


@safe
def selftest() -> int:
    """Headless bundle test: YOLO load + a capture + one full brain pass + planner."""
    from roadmind import config as C, capture, sys_utils
    from roadmind.perception import detector, pipeline
    from roadmind.planner.planner import Planner

    print("GameROBOT selftest")
    d = detector.Detector()
    print(f"  YOLO {d.model_name}: {'OK (%s)' % d.device if d.ready else 'FAILED'}")
    if not d.ready:
        print("  (weights not found - botched bundle)")
        return 1

    eng = pipeline.PerceptionEngine()
    st = pipeline.WorldState()
    try:
        cap = capture.WindowCapture((0, 0, 320, 240))
        frame = cap.grab()
        print(f"  capture: OK {frame.shape}")
    except Exception as e:
        frame = None
        print(f"  capture: FAILED ({e})")
    if frame is not None:
        eng._process(frame)
        print(f"  brain pass: dets={len(eng.state.dets)} "
              f"lanes={eng.state.lanes['valid']} "
              f"speed_limit={eng.state.speed_limit}")
    p = Planner(C.RoadMindConfig())
    allowed = {a for a in C.ACTIONS if True}
    dt = p.plan(st, allowed)
    print(f"  planner: mode={dt.mode}")
    print("SELFTEST OK")
    return 0


def _native_prompt(msg: str) -> bool:
    """True when the user chose 'Update now'. Replaceable in tests."""
    try:
        from roadmind import sys_utils
        r = sys_utils.native_dialog("GameROBOT update", msg,
                                    buttons=("Later", "Update now"),
                                    default="Update now")
        return r == "Update now"
    except Exception:
        return False


def startup_update_check() -> bool:
    """Run BEFORE the app opens. If a newer version exists, ask the user to
    update first; returns True when we should quit and let them update."""
    from roadmind import __version__ as cur, updater
    if "--noupdate" in sys.argv:
        return False
    latest, url, notes, newer = updater.check_once(timeout=6.0)
    if not newer:
        return False
    if not url:
        url = "https://github.com/mohammedahakimmk-beep/roadmind/releases"
    msg = (f"GameROBOT v{latest} is available (you have v{cur}).\n\n"
           f"{notes}\n\n"
           "Update now? The download page for the new build will open.")
    if not _native_prompt(msg):
        return False
    import webbrowser
    webbrowser.open(url)
    return True


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if "--doctor" in sys.argv:
        return doctor()
    if "--help" in sys.argv or "-h" in sys.argv:
        print("GameROBOT - open-source AI autopilot for driving games.\n"
              "  roadmind            launch the app (checks for updates first)\n"
              "  roadmind --doctor   check permissions + window detection\n"
              "  roadmind --selftest headless smoke test (good for a bundled build)\n"
              "  roadmind --noupdate skip the update prompt on launch")
        return 0
    if startup_update_check():
        return 0
    return run()


if __name__ == "__main__":
    raise SystemExit(main())