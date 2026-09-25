# Changelog

## v0.6.0 — smarter still: light-aware, occlusion-proof, tuneable

### Smarter AI
- **The bot actually reads the light.** Traffic lights are classified by their
  real color: red stops, **yellow eases off** ("cautious" mode, no slamming),
  green gets flagged "go" in the thinking ribbon. Light state now has a
  **freshness window (~1.3s)** — a stale "red" can no longer leave the car
  parked forever when the light disappears from view or the detector blinks.
- **Occlusion-resilient tracking.** When an object briefly vanishes behind a
  truck, lighting flicker or a detector hiccup, its box keeps gliding at the
  last measured velocity (constant-velocity coast) instead of strobing — and
  re-acquires the same ID when it reappears. Long-gone ghosts are dropped and
  don't count as threats.
- **WORLD TUNE (per-window FOV calibration).** New dashboard row with four
  live values: HORIZON (vanishing point), DISTANCE (depth scale), VANISH X and
  LANE ROI. Type + Enter and the depth/speed model, lane crop and the projected
  road in the vision view all re-baseline for that game.
- **VISION MODEL toggle.** YOLO size N / S / M pills on the dashboard. N is
  bundled with the EXE; S and M auto-download on first use and persist. Bigger
  models = better small-object detection at a CPU cost.

### Under the hood
- `Profile.world` + `Profile.model` persisted in config.json; tracker depth
  globals are tuneable per game via `tracker.set_world()`.
- Lane detector accepts a `horizon_y` crop; pipeline lanes honor the tuned ROI.
- Release pipeline gains (commented) scaffolding for Azure Trusted Signing so
  the SmartScreen warning can be removed once a cert exists — see README
  "Signing".
- 6 new unit tests covering world/model roundtrip, occlusion coasting +
  re-acquisition, light freshness expiry and yellow-light planning.

## v0.5.0 — GameROBOT rebrand + the 10x-smarter update

**The project is now GameROBOT** (the shipped EXE is `GameROBOT-0.5.0-Windows.exe`).

### Smarter AI
- **Every object understood, boxed and labelled.** Cars, people, trucks, buses,
  bikes, traffic lights and stop signs get a bounding box with a label chip
  above it: `CAR · EST SPEED: 60`, `HUMAN · EST SPEED: 6`. Per-object relative
  speed is measured with a projective world model (tracked over ~0.5s windows).
- **Human-aware driving.** People on the road ahead trigger gentle braking plus
  a cautious speed, with a "mindful" mode in the thinking log.
- **Smoother driving.** Throttle ramps up/down instead of snapping; steering is
  low-passed; leader picker now really picks the *closest* vehicle ahead.
- Live object census (e.g. `2 objs · CARx1 · PERSONx1`) in the telemetry panel;
  leader/human est speeds surface in the UI.

### New dashboard game menu
- Full-bleed animated menu: drifting particles, breathing glow title,
  rotating taglines, "WELCOME BACK, DRIVER".
- Live version pill (`v0.5.0 · Windows Edition · opensource`), target-game
  picker + refresh, permissions strip, vision-overlay settings card (boxes /
  est-speed / lanes / HUD toggles, target & max speed), and the big pulsing
  **▶ IGNITE ENGINE** button — no boring "START". Fade-flash transition into
  the cockpit.

### Alive cockpit
- Scan-line sweeping the vision view, pulsing LIVE dot, object-count +
  speed-limit readout on the top strip, animated ARM dots, per-object boxes
  with est-speed chips, person head-glow marker, motion streaks.
- Renamed brand, header ("GameROBOT"), viewport bottom strip, perm-help copy,
  ARM button ("ENGAGE AUTOPILOT").

### Under the hood
- Config gains `ui` preferences (persisted overlays toggles).
- Windows EXE renamed; release pipeline, manifest URL and update checks point
  at `GameROBOT-<v>-Windows.exe`.
- macOS DMG stays discontinued (v0.1.3 was the last); sources remain buildable.

## v0.4.0 — the UI overhaul, properly numbered

Renumbered release of the v0.3.0 UI work so the new build is clearly newer
than what you had. Same changes, one number higher:

- **Curved buttons.** Every button is now a rounded "pill" (canvas-drawn with
  hover + press states): ARM / CALIBRATE / PAUSE / STOP, the game refresh,
  the update banner, status chips, whitelist save.
- **The gameplay is now a proper box.** The live view sits inside a framed,
  rounded bezel (a dark "screen") with a crisp inner border, a LIVE/STANDBY
  badge, the game name and a bottom status strip — real product chrome with
  panels laid out around it.
- **Colour contrast fixed.** Unreadable dark-on-dark text is gone: a brighter,
  contrast-checked palette, readable text on green, amber and red pills.
- **Platform fonts.** Segoe UI on Windows / SF Pro on macOS; Consolas / Menlo.
- **Scrollable whitelist.** All 13 actions fit regardless of window height.
- macOS DMG remains discontinued/Windows-only.

## v0.3.0 — whole-UI overhaul ("finally looks like a real app")

- **Curved buttons.** Every button is now a rounded "pill" (canvas-drawn with
  hover + press states): ARM / CALIBRATE / PAUSE / STOP, the game refresh,
  the update banner, status chips, whitelist save.
- **The gameplay is now a proper box.** The live view sits inside a framed,
  rounded bezel (a dark "screen") with a crisp inner border, a LIVE/STANDBY
  badge, the game name and a bottom status strip — real product chrome with
  panels laid out around it.
- **Colour contrast fixed.** Unreadable dark-on-dark text is gone: a brighter,
  contrast-checked palette (FG/FG_DIM/FG_FAINT), readable text on green,
  amber and red pills, live chips that show ON (green) / OFF (red) clearly.
- **Platform fonts.** Segoe UI on Windows / SF Pro on macOS; monospace
  switches to Consolas / Menlo.
- **Scrollable whitelist.** All 13 actions fit regardless of window height.
- macOS DMG remains discontinued/Windows-only; branding and viewport updated.

## v0.2.0 — Windows EXE release (macOS DMG officially discontinued)

**Announcement:** RoadMind is now Windows-only. The macOS DMG line is
officially discontinued — **v0.1.3 is the last macOS build**.

Rationale: macOS TCC (Screen Recording / Input Monitoring / Accessibility)
grants are scoped to the code identity of the app, so every rebuilt DMG is a
"new app" whose grants silently reset; there is no admin bypass, and
Gatekeeper quarantine added another layer. Windows has none of those walls.

### What's new

- **Windows one-file EXE** (`RoadMind-<v>-Windows.exe`) — double-click to run;
  no install, no permissions, no admin.
- **Windows backends** — screen capture (mss), input injection
  (user32 VK codes), window picking + activation (win32), native dialogs
  (MessageBox). The tkinter UI, CV brain, planner and safety layer are
  unchanged and shared.
- **Launch-gated updates** still apply: the app checks GitHub before the
  window opens; Windows users are pointed straight at the EXE download.
- macOS sources remain buildable for developers; the DMG is no longer
  produced or released. `release.yml` now builds on a Windows runner.

## v0.1.3 — crash-proofing + launch-gated updates (macOS, last DMG)

- Every launch checks the GitHub manifest before the window opens and offers
  to update first (`--noupdate` for dev).
- Errors never die silently: native dialog + `crash.log`.
- YOLO weights embedded; `--selftest` validates the bundle.
- CI: weights fetched on the runner.

## v0.1.0 — initial release

- First public DMG with the full autopilot: whitelist, auto-calibration,
  YOLO vision, lane/flow perception, safety controls, Tesla-style overlay.