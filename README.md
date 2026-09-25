# GameROBOT

## Official announcement — the macOS DMG is discontinued

**GameROBOT (formerly RoadMind) is now a Windows app. The macOS DMG is
officially discontinued (v0.1.3 was the last macOS build).**

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
**Tesla-style vision overlay** of exactly what the AI sees and understands —
with a **bounding box and an EST-SPEED label above every car, person, bike
and sign** — remembers the road (speed limits, traffic lights, vehicles),
and drives through **only the controls you whitelist**.

No cloud. No teaching per game. Works on any game window you point it at.

It launches from a **game-menu dashboard**: WELCOME BACK, DRIVER, your current
version, settings, and one big **IGNITE ENGINE** button that drops you into the
cockpit.

## Features

- **Game-menu dashboard** — animated launcher with your version, target-game
  picker, permissions strip, vision-overlay settings and a pulsing
  IGNITE ENGINE button.
- **Smarter AI (v0.5.0+)** — every object the YOLO brain understands gets a
  bounding box + label chip: `CAR · EST SPEED: 60`, `HUMAN · EST SPEED: 6`…
  per-object relative speed is measured from a projective world model; the bot
  **brakes gently when a human is on the road**, ramps throttle smoothly,
  smooths steering, reads speed-limit signs + traffic lights, tracks its
  leader and keeps a safe gap.
- **Light-aware driving (v0.6.0)** — traffic lights are classified by their
  real color (red stops, yellow eases, green goes) with a freshness window, so
  a light that leaves view can't leave you parked anywhere.
- **Occlusion-proof tracking (v0.6.0)** — objects that blink behind a truck or
  a detection hiccup keep gliding at their last velocity and re-acquire the
  same ID, instead of strobing on and off.
- **WORLD TUNE (v0.6.0)** — per-window FOV calibration: horizon, distance
  scale, vanishing X and lane ROI, typed straight into the dashboard and
  applied live to the depth/speed model and the projected road.
- **VISION MODEL toggle (v0.6.0)** — YOLO size N (bundled) / S / M
  (auto-download) pills on the dashboard: accuracy vs CPU.
- **Whitelist gate** — before every drive you choose exactly which controls exit
  (throttle, brake, steering, blinkers, honk, ABS…). Unchecked → the AI is *blocked*
  from using that action.
- **Fully-automatic calibration** — GameROBOT probes each whitelisted key
  (holds it, measures the on-screen response with optical flow) and records
  latency + gain. Re-run for any game.
- **Local CV brain** — YOLO11n (vehicles / people / traffic lights / stop signs),
  circle-sign + OCR **speed-limit reader**, lane detection, sparse optical flow
  motion/speed estimate, per-object tracking with speed estimation — accelerated
  on GPU when available.
- **Memory & telemetry** — latches speed limits, traffic light state,
  leader-vehicle gaps, human alerts, motion history, and a live object census.
- **Animated Tesla-style view** — dimmed game frame + projected road, lane lines,
  object boxes with labels, a moving scan line, a live badge, the speed-limit
  dial and the AI's current intent.
- **Safety** — `ctrl+alt+Q` global kill, auto-pause when the game loses focus,
  release-everything on stop, speed clamps.
- **Launch-gated updates** — on every start the app checks GitHub for a newer
  version *before* the window opens and offers to update first.

## Install (Windows)

1. Download **`GameROBOT-<version>-Windows.exe`** from the
   [releases page](https://github.com/mohammedahakimmk-beep/roadmind/releases).
2. Run it. No install, no permissions, no admin.
3. Windows SmartScreen may warn about an unsigned EXE → *More info → Run anyway*
   (signing is on the roadmap).

The updater nags you automatically when a newer version is released.

## Use

1. **Dashboard** — pick your game window, tweak the vision overlays, size the
   AI model (N/S/M), tune the world values if the depth/est-speeds feel off
   for your game's FOV, then hit **IGNITE ENGINE**.
2. **Cockpit** — whitelist exactly the controls the AI may use (right panel).
3. **CALIBRATE** — park the car somewhere safe; GameROBOT auto-probes each key.
4. **ENGAGE AUTOPILOT** — watch the boxes, EST speeds and its thinking live.
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

`packaging/windows.spec` builds the one-file `GameROBOT.exe` with PyInstaller;
GitHub Actions (`release.yml`) does it automatically for every `v*` tag and
rewrites the version manifest. macOS packaging (`packaging/build_dmg.sh`) is
deprecated and unmaintained.

## Signing

The released EXE is unsigned, so Windows SmartScreen shows "Unknown publisher"
(*More info → Run anyway*). To remove that, sign the EXE with an Authenticode
certificate: the workflow has a ready-to-enable Azure Trusted Signing block
(commented in `release.yml`) — set the `ACS_*` repo secrets, uncomment the
step, and the next tagged build uploads a signed binary. A cheap
self-signed cert does **not** remove the SmartScreen warning, so only an
OV/EV commercial cert is worth it. This is an open-source project: we'd love a
sponsor who already has one.

## License

MIT. The YOLO model weights ship under Ultralytics' AGPL-3.0; see ultralytics.com.