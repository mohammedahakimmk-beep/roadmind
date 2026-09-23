"""Application entry point."""

from __future__ import annotations

import sys

sys.path.insert(0, "/Users/mohammed/Desktop/roadmind")


def run() -> int:
    from .ui.main_window import build_app
    app, _ = build_app()
    return app.mainloop()


def doctor() -> int:
    from . import sys_utils
    import Quartz
    listen = getattr(Quartz, "CGPreflightListenEventAccess", None)
    print("RoadMind doctor")
    print(f"  Accessibility   : {'GRANTED' if sys_utils.is_accessibility_trusted() else 'MISSING'}")
    print(f"  Screen capture  : {'GRANTED' if sys_utils.is_screen_capture_allowed() else 'MISSING'}")
    im = "GRANTED" if (listen and listen()) else "optional (needed for ctrl+alt+Q hotkey)"
    print(f"  Input monitoring: {im}")
    print("  Windows found  :", len(sys_utils.list_windows(min_w=200, min_h=200)))
    print("  Updates        : auto-checked at startup (GitHub manifest), silent on failure")
    return 0


def main() -> int:
    if "--doctor" in sys.argv:
        return doctor()
    if "--help" in sys.argv or "-h" in sys.argv:
        print("RoadMind - open-source AI autopilot for driving games.\n"
              "  roadmind            launch the app\n"
              "  roadmind --doctor   check macOS permissions + window detection")
        return 0
    return run()


if __name__ == "__main__":
    raise SystemExit(main())