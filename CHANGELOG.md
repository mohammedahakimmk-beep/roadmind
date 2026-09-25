# Changelog

## v0.6.4 — Bug fixes and improvements

- **The window you picked is now the window that's watched.** The picker no
  longer auto-selects the LARGEST window (often the desktop/`Program Manager`
  on Windows — the reason a "chosen" window could feed the whole screen). It
  filters out desktop/shell/OS-chrome windows and auto-picks the FRONT-MOST
  window (the game you just alt-tabbed to).
- **Vision status now shows the exact region** being captured: e.g. "watching
  1920x1080px" and - when the region fills the monitor - "(fills the screen -
  game is fullscreen/borderless, that's the whole game)". A fullscreen game's
  window genuinely IS the whole screen, so a full-screen capture there is
  correct behaviour, and now it's labelled as such.
- **Windows DPI fix**: the EXE now claims per-monitor DPI awareness BEFORE Tk
  opens, so window rects and screen grabs both use physical pixels. On a
  150%-scaled display a mismatched (DPI-unaware) rect could grab the wrong
  stretch of screen; that path is closed.
- 13 unit tests green; selftest inside the bundled EXE passes on CI; full GUI
  boot verified (picker → live capture on the front-most window).

## v0.6.3 — Bug fixes and improvements

- **Calibration is now required.** ENGAGE AUTOPILOT refuses to start until the
  throttle / brake / steer controls have been probed, and says *"Please calibrate
  first"* with the exact missing controls and why it needs them (it learns each
  key's latency + gain by watching the screen respond). The cockpit keeps a
  live amber **PRE-FLIGHT** line (e.g. `CALIBRATE REQUIRED: Throttle (gas),
  Brake, Steer left, Steer right`) and the ENGAGE button stays amber until you
  calibrate.
- **Windows "elevated game" now diagnosed.** If the game runs as Administrator,
  Windows silently blocks injected keystrokes (UIPI) — the bot can watch the
  full screen but the car never moves. GameROBOT now detects the elevated game,
  warns right after you pick it, blocks ENGAGE with *"run GameROBOT as
  Administrator"*, and shows it in the PRE-FLIGHT line.
- **Live preflight explains why the car isn't moving** — calibration, missing
  steering/throttle keys in the whitelist, macOS Accessibility grant, no
  window target — shown in plain words under the control bar and re-checked a
  few times a second.
- Permission help (?) now documents the Windows admin case and the rare
  raw-input/anti-cheat game that ignores synthetic keys (rebind in-game there).
- 13 unit tests green; selftest inside the bundled EXE passes on CI.

## v0.6.2 — Bug fixes and improvements

- Fixed an immediate crash on Windows: the UI used the macOS-only cursor name
  `pointinghand`, which Windows Tk rejects (`bad cursor spec`), killing the
  dashboard at launch. Now uses the cross-platform `hand2` everywhere.
- Cursor assignment is also guarded so a cosmetic cursor problem can never take
  the app down again.

## v0.6.1 — hazard lights, empty-key controls, clearer whitelist

- **Hazard lights added** to the control set (default key `p`). The AI now
  flashes them when it stands hard on the brakes because a car is right there
  (or on a full stop), and hazards override blinkers while they flash. Turn the
  toggle off in the whitelist to silence them; an empty key disables them too.
- **Empty KEY = the game has no such control.** If a game doesn't have a
  blinker, a hazard button or ABS, just leave the KEY field empty — the bot
  skips that action entirely and the whitelist checkbox auto-clears. Previously
  an unbound key still counted as "allowed" and sent an empty keypress.
- **Clearer whitelist UX.** Each control shows a dim `—` placeholder when no
  key is set, and an explanatory line sits under the WHITELIST header.
- Blinkers (left/right, default ←/→) were already there — this release adds the
  single-button control and makes "no control" explicit.

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