"""GameROBOT app: a dashboard launcher that drops you into the autopilot cockpit.

Structure:
  MainWindow        - Tk root; owns the brain (perception engine, planner,
                      controller, safety, capture) and the two scenes.
  DashboardScene    - game-menu launcher: welcome back, version, settings,
                      target game, the big IGNITE ENGINE button.
  CockpitScene      - the driving UI: live vision bezel, perms chips,
                      whitelist/telemetry panels, ARM / CALIBRATE / PAUSE /
                      STOP controls.

Both scenes read the same brain; switching keeps arms/capture alive.
"""

from __future__ import annotations

import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .. import calibrate, capture, config as C, input_ctl, safety, sys_utils, updater
from .. import __version__
from ..perception import pipeline
from ..planner import controller as ctlmod
from ..planner.planner import Planner
from . import theme as T
from .dashboard import DashboardScene
from .panels import MemoryPanel, StatusChips, WhitelistPanel
from .road_view import RoadView


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GameROBOT \u00b7 AI Autopilot")
        self.geometry("1360x860")
        self.minsize(1120, 760)
        self.configure(bg=T.BG_DEEP, padx=0, pady=0)

        self.cfg = C.RoadMindConfig()
        self.engine = pipeline.PerceptionEngine(self.cfg)
        self.planner = Planner(self.cfg)
        self.controller = ctlmod.Controller(self.cfg)
        self.safety = safety.Safety()
        self.capture = None
        self.game_owner = ""
        self.game_pid = 0
        self.armed = False
        self._armed_at = 0.0
        self._last_plan_t = 0.0
        self._events = queue.Queue()
        self._updater = None
        self._tick_no = 0
        self._perm_cache = (None, False, False, False)
        self._wins = []
        self._cp = None
        self._dash = None

        self.stage = tk.Frame(self, bg=T.BG_DEEP)
        self.stage.pack(fill="both", expand=True)

        self._configure_style()
        self._build_dashboard()
        self._refresh_windows()
        self.safety.start(on_kill=lambda: self._events.put("kill"))
        self._start_update_check()
        self.after(40, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- style ------------------------------------------------
    def _configure_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TCombobox",
                    fieldbackground=T.PANEL2, background=T.PANEL2,
                    foreground=T.FG, arrowcolor=T.ACC,
                    bordercolor=T.LINE, lightcolor=T.PANEL2,
                    darkcolor=T.PANEL2, selectbackground=T.PANEL2,
                    selectforeground=T.FG)
        s.map("TCombobox", fieldbackground=[("readonly", T.PANEL2)])
        s.configure("TProgressbar", background=T.ACC, troughcolor=T.PANEL,
                    bordercolor=T.PANEL, lightcolor=T.ACC, darkcolor=T.ACC)

    # ---------------- scenes ------------------------------------------------
    def _build_dashboard(self):
        if self._cp is not None:
            self._cp.stop()
            self._cp.destroy()
            self._cp = None
        self._dash = DashboardScene(self.stage, self)
        self._dash.pack(fill="both", expand=True)
        self._refresh_windows()

    def launch(self):
        """IGNITE ENGINE: fade-flash into the cockpit."""
        if self._cp is not None:
            return
        steps = [1.0, 0.82, 0.66, 0.5]
        n = 0

        def _go():
            nonlocal n
            if n < len(steps):
                self.wm_attributes("-alpha", steps[n])
                n += 1
                self.after(42, _go)
            else:
                self._build_cockpit()
                self.wm_attributes("-alpha", 1.0)
                self.after(120, lambda: self._fade_in())
        _go()

    def _fade_in(self):
        steps = [0.7, 0.85, 1.0]
        n = 0

        def _go():
            nonlocal n
            if n < len(steps):
                self.wm_attributes("-alpha", steps[n])
                n += 1
                self.after(42, _go)
        _go()

    def _build_cockpit(self):
        if self._dash is not None:
            self._dash.stop()
            self._dash.destroy()
            self._dash = None
        self._cp = CockpitScene(self.stage, self)
        self._cp.pack(fill="both", expand=True)
        self._refresh_windows()
        self._refresh_preflight()

    # ---------------- world tune + model swap ------------------------------------
    def apply_world(self):
        """Push WORLD TUNE into the depth/lane models and the vision view."""
        self.engine.apply_world()
        if self._cp is not None:
            self._cp.view.set_world(self.cfg.profile.world)
            self._set_status("World tune applied \u00b7 restart vision on the "
                             "game window to fully re-baseline")

    def apply_model(self, size: str):
        if size not in C.MODEL_SIZES:
            return
        self.engine.set_model(size)
        note = "VISION MODEL switched" + (
            "" if size == "n" else
            " \u00b7 S/M weights download on first use (bundled N is instant)")
        self._set_status(note)

    # ---------------- updater ------------------------------------------------
    def _start_update_check(self):
        self._updater = updater.Updater(on_result=self._on_update)
        self._updater.poll()

    def _on_update(self, latest, url, notes):
        if self._cp is None:
            return
        self._cp.update_available(latest, url, notes)

    # ---------------- game window picking -------------------------------------
    def refresh_games(self):
        self._refresh_windows()

    def _refresh_windows(self):
        wins = capture.list_game_windows()
        self._wins = wins
        labels = [w["owner"] + (f" - {w['name']}" if w["name"] else "") for w in wins]
        if self._cp is not None:
            self._cp.set_windows(labels)
        if self._dash is not None:
            self._dash.set_windows(labels)

    def pick_game_at(self, idx: int):
        if idx < 0 or idx >= len(self._wins):
            return
        w = self._wins[idx]
        self.game_owner = w["owner"]
        self.game_pid = w.get("pid", 0)
        if self._cp is not None:
            self._cp.view.game_label = w["owner"] + \
                (f" - {w['name']}" if w["name"] else "")
        self.disarm()
        self.engine.stop()
        self.capture = capture.WindowCapture((w["x"], w["y"], w["w"], w["h"]))
        self.engine.start(self.capture)
        parts = [
            f"Vision active on [{w['owner']}]",
            f"screen={'ok' if sys_utils.is_screen_capture_allowed() else 'grants missing'}",
            f"keyboard={'ok' if sys_utils.is_accessibility_trusted() else 'grants missing'}",
        ]
        ok, _why = sys_utils.game_elevation_ok(self.game_pid)
        if not ok:
            parts.append("WARN: game is elevated - run GameROBOT as Administrator "
                         "or keys won't reach it (car won't move)")
        self._set_status(" \u00b7 ".join(parts))
        self._refresh_preflight()

    def _on_pick_window(self, ev=None):
        if self._cp is not None:
            self.pick_game_at(self._cp.win_combo.current())
        elif self._dash is not None:
            self.pick_game_at(self._dash._win_combo.current())

    def _set_status(self, text):
        if self._cp is not None:
            self._cp.set_status(text)
        elif self._dash is not None:
            self._dash.set_status(text)

    def _require_calibration(self):
        miss = self.cfg.missing_calibration()
        if not miss:
            return ""
        return ("GameROBOT won't drive before it learns how YOUR game responds.\n\n"
                "Calibration briefly holds each drive control key and watches the "
                "screen move (optical flow) to measure latency + gain. Without those "
                "numbers the bot can't tell whether a keypress worked - so it stays "
                "parked instead of driving blind.\n\n"
                "Not probed yet: " + ", ".join(miss) + "\n\n"
                "What to do:\n"
                "  1. Start the game, stop somewhere safe and open, keep it front-most.\n"
                "  2. In the cockpit, click CALIBRATE (auto probe, ~10 seconds).\n"
                "  3. Then press ENGAGE AUTOPILOT again.\n\n"
                "Re-run it for each game - every game responds differently.")

    # ---------------- autopilot ------------------------------------------------
    def arm(self):
        if not self.capture:
            messagebox.showwarning("No target", "Pick a game window first.")
            return
        cal_msg = self._require_calibration()
        if cal_msg:
            messagebox.showwarning("Please calibrate first", cal_msg)
            return
        if sys_utils.requires_accessibility() and not sys_utils.is_accessibility_trusted():
            messagebox.showwarning(
                "Keyboard blocked \u2014 one fix",
                "GameROBOT needs the Accessibility permission to send keyboard "
                "input. If the KEYBOARD status chip says OFF above, click it to "
                "open System Settings and:\n\n"
                "  1. find the app you launch GameROBOT with (your terminal, or "
                "GameROBOT.app for the .dmg)\n"
                "  2. switch it OFF, then back ON (macOS glitch)\n"
                "  3. quit that app completely and relaunch it\n\n"
                "The chips refresh by themselves \u2014 no restart needed.")
            return
        ok_elev, elev_msg = sys_utils.game_elevation_ok(self.game_pid)
        if not ok_elev:
            messagebox.showwarning("Game runs as Administrator", elev_msg)
            return
        messagebox.showinfo(
            "Before you ARM",
            "1. Make sure the game is FRONT-MOST (fullscreen/exclusive).\n"
            "   Autopilot pauses automatically if the game loses focus.\n"
            "2. Put the car somewhere SAFE (open road / parking).\n"
            "3. Only whitelisted controls are used.\n\n"
            "ctrl+alt+Q stops everything instantly.\n\n"
            "After clicking OK, click into the game once.")
        if self.game_pid:
            sys_utils.activate_pid(self.game_pid)
        self.armed = True
        self._armed_at = time.time()
        if self._cp is not None:
            self._cp.set_arm_state(True, f"ENGAGED \u00b7 watching [{self.game_owner}]")
            self._cp.view.armed = True
        self.controller.arm()

    def disarm(self):
        if self.armed:
            input_ctl.release_all()
        self.armed = False
        if self._cp is not None:
            self._cp.set_arm_state(False, "Autopilot paused \u2014 vision still running.")
            self._cp.view.armed = False
        self.controller.disarm()

    def _hard_stop(self):
        input_ctl.release_all()
        self.disarm()
        self._set_status("STOP pressed \u2014 released all input")

    def _preflight(self):
        """Issue list explaining, in plain words, exactly why the car may not move."""
        issues = []
        miss = self.cfg.missing_calibration()
        if miss:
            issues.append("CALIBRATE REQUIRED: " + ", ".join(miss) +
                          " - click CALIBRATE below first")
        if {"throttle", "steer_left", "steer_right"} & {
                a for a in C.ACTIONS if self.cfg.allowed(a)} == set():
            issues.append("WHITELIST: no steering/throttle keys - tick them on")
        if self.capture is None:
            issues.append("NO TARGET: pick your game window first")
        if self.game_pid and sys_utils.requires_accessibility() \
                and not sys_utils.is_accessibility_trusted():
            issues.append("KEYBOARD OFF: macOS Accessibility grant missing - "
                          "tick the chip above")
        if self.game_pid:
            ok, _why = sys_utils.game_elevation_ok(self.game_pid)
            if not ok:
                issues.append("ELEVATED GAME: run GameROBOT as Administrator - "
                              "Windows blocks keys into an elevated game")
        return issues

    def _refresh_preflight(self):
        if self._cp is not None:
            self._cp.set_preflight(self._preflight())

    # ---------------- calibration ------------------------------------------------
    def _launch_calibration(self):
        if self.armed:
            self.disarm()
        if not self.capture:
            messagebox.showwarning("No target", "Select a game window first.")
            return
        if sys_utils.requires_accessibility() and not sys_utils.is_accessibility_trusted():
            messagebox.showwarning("Keyboard blocked",
                                   "Accessibility is required to send keys during "
                                   "calibration. Fix it from the KEYBOARD chip above.")
            return
        if self._cp is None:
            return
        messagebox.showinfo(
            "Calibration",
            "Fully-automatic probe: GameROBOT will hold each whitelisted key briefly "
            "and measure latency + response with optical flow.\n\n"
            "Make sure the car is in a safe open spot and the game window keeps focus.")
        self._cp.progress_on()
        self.wiz = calibrate.CalibrationWizard(
            self.cfg, self.capture,
            on_step=self._cal_step,
            on_done=self._cal_done,
            on_error=lambda e: self._set_status("calibration error: " + str(e)),
            on_progress=self._cal_progress)
        self.wiz.run()

    def _cal_step(self, action, msg):
        self._set_status(msg)

    def _cal_progress(self, frac):
        if self._cp is not None:
            self._cp.progress["value"] = int(frac * 100)

    def _cal_done(self, results):
        if self._cp is not None:
            self._cp.progress.pack_forget()
            self._cp.progress_off()
        self._set_status("Calibration saved: " + ", ".join(
            f"{a}={c.latency_ms:.0f}ms" for a, c in results.items()))

    # ---------------- main loop ------------------------------------------------
    def _drain_events(self):
        while True:
            try:
                ev = self._events.get_nowait()
            except queue.Empty:
                return
            if ev == "kill":
                self._hard_stop()
                self._set_status("KILL SWITCH \u2014 released all input")

    def _refresh_perms(self):
        """Lightweight permission re-read (~4x/sec). Returns True when changed."""
        input_ok = sys_utils.is_accessibility_trusted()
        screen_ok = sys_utils.is_screen_capture_allowed()
        hotkey_ok = sys_utils.input_monitoring_allowed()
        vision_ok = self.engine.frame is not None
        cur = (input_ok, screen_ok, hotkey_ok, vision_ok)
        if cur != self._perm_cache:
            self._perm_cache = cur
            if self._cp is not None:
                self._cp.chips.refresh(input_ok, screen_ok, hotkey_ok, vision_ok)
            elif self._dash is not None:
                self._dash.set_perms(input_ok, screen_ok, hotkey_ok)
            return True
        return False

    def _tick(self):
        self._drain_events()
        self._tick_no += 1
        if self._tick_no % 10 == 0:
            self._refresh_perms()
            self._refresh_preflight()
        if self._cp is None:
            self.after(40, self._tick)
            return
        st = self.engine.state
        if self.engine.frame is not None:
            self._cp.view.set_frame(self.engine.frame, st)
            self._cp.view._draw()
        if st is not None:
            self._cp.mem.update_state(st, self.engine.mem, self.armed)

        if self.armed:
            now = time.time()
            focus_ok = (now - self._armed_at) < 2.5
            if not focus_ok and safety.game_window_lost_focus(self.game_owner):
                self._set_status("Game lost focus \u2014 autopilot paused.")
                self.disarm()
            else:
                if focus_ok and (now - self._armed_at) < 1.2 and self.game_pid:
                    sys_utils.activate_pid(self.game_pid)
                if now - self._last_plan_t > 0.1:
                    allowed = {a for a in C.ACTIONS if self.cfg.allowed(a)}
                    if not ({"throttle", "steer_left", "steer_right"} & allowed):
                        self._set_status("No steering/throttle whitelisted.")
                    else:
                        dt = self.planner.plan(st, allowed)
                        st.plan = dt
                        st.thinking = dt.reason
                        self.controller.set_plan(dt)
                        self._last_plan_t = now
        self.after(40, self._tick)

    def _on_close(self):
        input_ctl.release_all()
        self.controller.disarm()
        self.engine.stop()
        self.safety.stop()
        if self._cp is not None:
            self._cp.stop()
        if self._dash is not None:
            self._dash.stop()
        self.destroy()


class CockpitScene(tk.Frame):
    """The driving UI (dashboard -> IGNITE -> here)."""

    def __init__(self, master, app):
        super().__init__(master, bg=T.BG_DEEP)
        self.app = app
        self._build_ui()
        self._progress_visible = False

    # ---------------- UI -----------------------------------------------------
    def _build_ui(self):
        head = T.frame(self, bg=T.BG_DEEP)
        head.pack(fill="x", padx=16, pady=(12, 6))
        T.label(head, text="GameROBOT", bg=T.BG_DEEP, fg=T.ACC,
                font=T.BRAND).pack(side="left")
        T.label(head, text=f"  v{__version__}  \u00b7 AI autopilot for driving games",
                bg=T.BG_DEEP, fg=T.FG_FAINT, font=T.UI_SM).pack(side="left", padx=(8, 20))
        T.label(head, text="GAME", bg=T.BG_DEEP, fg=T.FG_DIM,
                font=T.UI_SM_B).pack(side="left", padx=(0, 8))
        self.win_combo = ttk.Combobox(head, width=38, state="readonly",
                                      font=T.UI, foreground=T.FG)
        self.win_combo.pack(side="left")
        self.win_combo.bind("<<ComboboxSelected>>", self.app._on_pick_window)
        T.button(head, text="\u21bb", command=self.app.refresh_games, bg=T.PANEL2,
                 active=T.darken(T.PANEL2, 0.2), font=T.UI_B, padx=8, pady=3)\
            .pack(side="left", padx=6)
        self._update_btn = T.button(head, text="", command=None, bg=T.ACC,
                                    fg=T.GO_DARK, font=(T.UI[0], 9, "bold"),
                                    padx=12, pady=5)
        self._update_url = ""
        self._update_notes = ""
        T.label(head, text="ctrl+alt+Q = emergency stop", bg=T.BG_DEEP,
                fg=T.ACC2, font=T.UI_SM_B).pack(side="right", padx=(0, 4), pady=4)
        self._update_btn.pack(side="right", padx=(0, 12))

        self.chips = StatusChips(self)
        self.chips.pack(fill="x", padx=16, pady=(2, 8))

        body = tk.PanedWindow(self, orient="horizontal", bg=T.BG_DEEP,
                              sashwidth=10, bd=0, sashrelief="flat",
                              background=T.BG_DEEP)
        body.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self.viewport = T.RoundedPanel(body, radius=18)
        body.add(self.viewport, minsize=540, stretch="always")
        self.view = RoadView(self.viewport, prefs=self.app.cfg.profile.ui,
                             world=self.app.cfg.profile.world)
        self.view.pack(fill="both", expand=True, padx=self.viewport.pad,
                       pady=self.viewport.pad)

        right = T.frame(body, bg=T.BG_DEEP)
        body.add(right, minsize=340)
        self.mem = MemoryPanel(right)
        self.mem.pack(fill="x", pady=(0, 10))
        self.whitelist = WhitelistPanel(right, self.app.cfg)
        self.whitelist.pack(fill="both", expand=True)

        bar = T.frame(self, bg=T.BG_DEEP)
        bar.pack(fill="x", padx=16, pady=(4, 14))
        self.btn_arm = T.button(bar, text="ENGAGE AUTOPILOT", command=self.app.arm,
                                bg="#0f9a63", fg="#062c1b", font=(T.UI[0], 12, "bold"),
                                padx=22, pady=10)
        self.btn_arm.pack(side="left")
        T.button(bar, text="CALIBRATE", command=self.app._launch_calibration,
                 bg=T.PANEL2, active=T.darken(T.PANEL2, 0.2), fg=T.FG,
                 font=T.UI_B, padx=16, pady=10).pack(side="left", padx=10)
        T.button(bar, text="PAUSE", command=self.app.disarm,
                 bg=T.AMBER, fg=T.WARN_TEXT, font=T.UI_B, padx=16, pady=10)\
            .pack(side="left", padx=10)
        T.button(bar, text="STOP ALL INPUT", command=self.app._hard_stop,
                 bg=T.RED, fg="#ffe6e9", font=T.UI_B, padx=16, pady=10)\
            .pack(side="left", padx=(10, 16))
        self.progress = ttk.Progressbar(bar, length=120, mode="determinate")
        self.status = T.label(bar, "Pick your game window to start vision.",
                              font=T.UI, fg=T.FG_DIM, bg=T.BG_DEEP)
        self.status.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self._hint = T.label(self, "", font=T.UI_SM_B, fg=T.FG_DIM, bg=T.BG_DEEP,
                             justify="left", wraplength=1080)
        self._hint.pack(fill="x", padx=16, pady=(0, 10))

    # ---------------- callbacks ---------------------------------------------
    def set_windows(self, labels):
        self.win_combo.configure(state="normal")
        self.win_combo["values"] = labels
        self.win_combo.configure(state="readonly")
        if labels:
            self.win_combo.current(0)
        self.btn_arm.configure(state="normal" if labels else "disabled")

    def set_status(self, text):
        self.status.configure(text=text)

    def set_arm_state(self, armed: bool, status_text: str):
        self.btn_arm.configure(state="disabled" if armed else "normal",
                               text="ENGAGED \u25c9" if armed else "ENGAGE AUTOPILOT")
        self.status.configure(text=status_text)

    def set_preflight(self, issues):
        if not issues:
            self._hint.configure(text="PRE-FLIGHT: READY \u2022 pick a window, "
                                      "CALIBRATE once if asked, then ENGAGE",
                                 fg=T.FG_DIM, bg=T.BG_DEEP)
            self.btn_arm.configure(bg="#0f9a63")
        else:
            self._hint.configure(text="PRE-FLIGHT: " + " \u2022 ".join(issues),
                                 fg=T.AMBER, bg=T.BG_DEEP)
            if any(i.startswith("CALIBRATE") for i in issues) \
                    and self.app.armed is False:
                self.btn_arm.configure(bg=T.AMBER)

    def update_available(self, latest, url, notes):
        self._update_url = url or ""
        self._update_notes = notes or ""
        self._update_btn.configure(
            text=f"\u2302  Update to v{latest}",
            command=lambda: self._ask_update(latest))
        self._update_btn.pack(side="right", padx=(0, 12))

    def _ask_update(self, latest):
        if messagebox.askyesno(
                "Update available",
                f"A newer GameROBOT is out (v{latest}, you have {__version__}).\n\n"
                f"{self._update_notes}\n\n"
                "Open the download page for the new build?"):
            updater.open_release(self._update_url or
                                 "https://github.com/mohammedahakimmk-beep/roadmind/releases")

    def progress_on(self):
        if not self._progress_visible:
            self.progress.pack(side="left", padx=(0, 10))
            self._progress_visible = True

    def progress_off(self):
        if self._progress_visible:
            self.progress.pack_forget()
            self._progress_visible = False

    def stop(self):
        pass


def build_app() -> tuple["MainWindow", None]:
    win = MainWindow()
    return win, None