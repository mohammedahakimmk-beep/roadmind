# RoadMind

Open-source **AI autopilot for driving games on macOS**. It watches the game window on
your screen with a **fully-local computer-vision brain**, shows a **Tesla-style
3D vision overlay** of what it sees and what it's thinking, remembers the road
(speed limits, traffic lights, vehicles), and drives through **only the controls
you whitelist**.

No cloud. No teaching per game. Works on any game window you point it at.

## Features

- **Whitelist gate** — before every drive you choose exactly which controls exist
  (throttle, brake, steering, blinkers, honk, ABS…). Unchecked → the AI is *blocked*
  from using that action.
- **Fully-automatic calibration** — RoadMind probes each whitelisted key
  (holds it, measures the on-screen response with optical flow) and records
  latency + gain. Re-run for any game.
- **Local CV brain** — YOLO11n (vehicles / people / traffic lights / stop signs),
  circle-sign + OCR **speed-limit reader**, native Apple Vision OCR, lane detection,
  sparse optical flow motion/speed estimate — all on the Metal (MPS) accelerator.
- **Memory** — latches speed limits, traffic light state, leader-vehicle gaps,
  motion history, and shows everything in the telemetry panel.
- **Tesla-style view** — the live game frame plus a projected 3D road, lane lines,
  wireframe vehicles, sign marks, speed-limit dial, and the AI's current intent.
- **Safety** — `ctrl+alt+Q` global kill, auto-pause when the game loses focus,
  release-everything on stop, speed clamps.

## Install / run (dev)

Requires macOS, Homebrew Python 3.12 + `python-tk` (GUI toolkit), ~1.5 GB for deps.

```bash
brew install python@3.12 python-tk@3.12
python3.12 -m venv .venv
.venv/bin/pip install -e .
./run.sh                          # or: .venv/bin/python -m roadmind
.venv/bin/python -m roadmind --doctor   # check permissions + window detection
```

On first launch grant **Screen Recording** and **Accessibility** to the terminal /
process running RoadMind (RoadMind links buttons to the right System Settings panes).
The first YOLO inference takes a few seconds (Metal kernel warm-up + model download); after that each frame is ~35 ms.

## Use

1. Pick your game window from the dropdown (top bar).
2. Whitelist exactly the controls the AI may use (right panel).
3. **CALIBRATE** — park the car somewhere safe; RoadMind auto-probes each key.
4. **ARM AUTOPILOT** — watch the Tesla-style vision and its thinking in real time.
5. `ctrl+alt+Q` anywhere to kill everything instantly.

## Packaging

`packaging/build_dmg.sh` builds a `.app` via PyInstaller and wraps it in a DMG.
Ad-hoc signing by default (fine for your machine); set
`ROADMIND_SIGN_IDENTITY` + Apple notary credentials for real distribution.

## License

MIT. The YOLO model weights ship under Ultralytics' AGPL-3.0; see ultralytics.com.