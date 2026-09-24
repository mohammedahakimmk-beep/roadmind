# RoadMind

## Official announcement — the macOS DMG is discontinued

**RoadMind is now a Windows app. The macOS DMG is officially discontinued
(v0.1.3 was the last macOS build).**

Why? macOS's TCC/Gatekeeper quarantine makes *even a permission-clean build*
unreliable — every rebuilt bundle is a "new app" to macOS, so the Screen
Recording / Input Monitoring / Accessibility grants silently reset, and there
is no admin-level bypass. That treadmill doesn't apply on Windows: **one
self-contained EXE, zero permissions, zero install**.

Download the current Windows EXE from the
[releases page](https://github.com/mohammedahakimmk-beep/roadmind/releases).

---

Open-source **AI autopilot for driving games**. It watches the game window on
your screen with a **fully-local computer-vision brain**, shows a
**Tesla-style 3D vision overlay** of what it sees and what it's thinking,
remembers the road (speed limits, traffic lights, vehicles), and drives
through **only the controls you whitelist**.

No cloud. No teaching per game. Works on any game window you point it at.

## Features

- **Whitelist gate** — before every drive you choose exactly which controls exit
  (throttle, brake, steering, blinkers, honk, ABS…). Unchecked → the AI is *blocked*
  from using that action.
- **Fully-automatic calibration** — RoadMind probes each whitelisted key
  (holds it, measures the on-screen response with optical flow) and records
  latency + gain. Re-run for any game.
- **Local CV brain** — YOLO11n (vehicles / people / traffic lights / stop signs),
  circle-sign + OCR **speed-limit reader**, lane detection, sparse optical flow
  motion/speed estimate — accelerated on GPU when available.
- **Memory** — latches speed limits, traffic light state, leader-vehicle gaps,
  motion history, and shows everything in the telemetry panel.
- **Tesla-style view** — the live game frame plus a projected 3D road, lane lines,
  wireframe vehicles, sign marks, speed-limit dial, and the AI's current intent.
- **Safety** — `ctrl+alt+Q` global kill, auto-pause when the game loses focus,
  release-everything on stop, speed clamps.
- **Launch-gated updates** — on every start the app checks GitHub for a newer
  version *before* the window opens and offers to update first.

## Install (Windows)

1. Download **`RoadMind-<version>-Windows.exe`** from the
   [releases page](https://github.com/mohammedahakimmk-beep/roadmind/releases).
2. Run it. No install, no permissions, no admin.
3. Windows SmartScreen may warn about an unsigned EXE → *More info → Run anyway*
   (signing is on the roadmap).

The updater nags you automatically when a newer version is released.

## Use

1. Pick your game window from the dropdown (top bar).
2. Whitelist exactly the controls the AI may use (right panel).
3. **CALIBRATE** — park the car somewhere safe; RoadMind auto-probes each key.
4. **ARM AUTOPILOT** — watch the Tesla-style vision and its thinking in real time.
5. `ctrl+alt+Q` anywhere to kill everything instantly.

## Install / run (dev)

Requires Python 3.12 + Tk, ~1.5 GB for deps.

```bash
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m roadmind                     # GUI (dev mode)
.venv\Scripts\python -m roadmind --doctor           # window detection check
.venv\Scripts\python -m roadmind --selftest         # headless smoke test
```

The macOS sources remain buildable (`./run.sh`) for developers, but no new
macOS binaries are released.

## Packaging

`packaging/windows.spec` builds the one-file EXE with PyInstaller; GitHub
Actions (`release.yml`) does it automatically for every `v*` tag and rewrites
the version manifest. macOS packaging (`packaging/build_dmg.sh`) is deprecated
and unmaintained.

## License

MIT. The YOLO model weights ship under Ultralytics' AGPL-3.0; see ultralytics.com.