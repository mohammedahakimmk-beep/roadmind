# Changelog

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