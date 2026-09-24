"""RoadMind main window (Tk): arm/disarm, calibration, Tesla vision, telemetry."""

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
from .panels import MemoryPanel, StatusChips, WhitelistPanel
from .road_view import RoadView


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"RoadMind AI Autopilot")
        self.geometry("1300x820")
        self.configure(bg=T.BG_DEEP, padx=0, pady=0)

        self.cfg = C.RoadMindConfig()
        self.engine = pipeline.PerceptionEngine()
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
        self._update_btn = None
        self._updater = None
        self._tick_no = 0
        self._perm_cache = (None, False, False, False)

        self._configure_style()
        self._build_ui()
        self._refresh_perms()
        self.safety.start(on_kill=lambda: self._events.put("kill"))
        self._refresh_windows()
        self._start_update_check()
        self.after(40, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- style ----------------
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

    # ---------------- UI ----------------
    def _build_ui(self):
        # ---- header ----
        head = T.frame(self, bg=T.BG_DEEP)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="ROADMIND", bg=T.BG_DEEP, fg=T.ACC,
                 font=("SF Pro Display", 17, "bold")).pack(side="left")
        tk.Label(head, text=f"  v{__version__}  \u00b7 open-source autopilot for driving games",
                 bg=T.BG_DEEP, fg=T.FG_FAINT, font=T.UI_SM).pack(side="left", padx=(6, 18))
        tk.Label(head, text="GAME", bg=T.BG_DEEP, fg=T.FG_FAINT,
                 font=T.UI_SM_B).pack(side="left", padx=(0, 6))
        self.win_combo = ttk.Combobox(head, width=40, state="readonly",
                                      font=T.UI, foreground=T.FG)
        self.win_combo.pack(side="left")
        self.win_combo.bind("<<ComboboxSelected>>", self._on_pick_window)
        T.button(head, text="\u21bb", command=self._refresh_windows, bg=T.PANEL2,
                 active="#2e3b66", font=T.UI_B, padx=8, pady=3).pack(side="left", padx=6)
        self._update_btn = tk.Button(head, bg=T.ACC, fg="#06121a", relief="flat", bd=0,
                                     font=(T.UI[0], 9, "bold"), padx=12, pady=5,
                                     cursor="pointinghand", activebackground=T.ACC,
                                     activeforeground="#06121a")
        self._update_url = ""
        tk.Label(head, text="ctrl+alt+Q = emergency stop", bg=T.BG_DEEP,
                 fg="#4dd6ff", font=T.UI_SM_B).pack(side="right")
        self._update_btn.lift()
        self._update_btn.pack(side="right", padx=(0, 12))

        # ---- status chips (live permission readout) ----
        self.chips = StatusChips(self)
        self.chips.pack(fill="x", padx=14, pady=(2, 6))

        # ---- body ----
        body = tk.PanedWindow(self, orient="horizontal", bg=T.BG_DEEP,
                              sashwidth=8, bd=0, sashrelief="flat")
        body.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        self.view = RoadView(body)
        body.add(self.view, minsize=520, stretch="always")

        right = T.frame(body, bg=T.BG)
        body.add(right, minsize=330)
        self.mem = MemoryPanel(right)
        self.mem.pack(fill="x", pady=(0, 10))
        self.whitelist = WhitelistPanel(right, self.cfg)
        self.whitelist.pack(fill="both", expand=True)

        # ---- control bar ----
        bar = T.frame(self, bg=T.BG_DEEP)
        bar.pack(fill="x", padx=14, pady=(0, 12))
        self.btn_arm = T.button(bar, text="ARM AUTOPILOT", command=self.arm,
                                bg="#0f8f60", active="#12b878", hover="#12b878",
                                fg="#eafff3", font=(T.UI[0], 12, "bold"), padx=20, pady=9)
        self.btn_arm.pack(side="left")
        self.btn_cal = T.button(bar, text="CALIBRATE", command=self._launch_calibration,
                                bg=T.PANEL2, active="#2e3b66", fg=T.FG,
                                font=T.UI_B, padx=16, pady=9)
        self.btn_cal.pack(side="left", padx=8)
        self.btn_disarm = T.button(bar, text="PAUSE", command=self.disarm,
                                   bg="#b07a12", active="#c98e1a", fg="#1b1204",
                                   font=T.UI_B, padx=16, pady=9)
        self.btn_disarm.pack(side="left", padx=8)
        self.btn_stop = T.button(bar, text="STOP ALL INPUT", command=self._hard_stop,
                                 bg="#b32733", active="#d03846", fg="#ffe9ec",
                                 font=T.UI_B, padx=16, pady=9)
        self.btn_stop.pack(side="left", padx=(8, 14))
        self.progress = ttk.Progressbar(bar, length=120, mode="determinate")
        self._progress_on = False
        self.status = T.label(bar, "Select your game window to start vision.",
                              font=T.UI_SM, fg=T.FG_DIM, bg=T.BG_DEEP)
        self.status.pack(side="left", fill="x", expand=True)

    # ---------------- updater ----------------
    def _start_update_check(self):
        self._updater = updater.Updater(on_result=self._on_update)
        self._updater.poll()

    def _on_update(self, latest, url, notes):
        self._update_url = url or ""
        self._update_notes = notes or ""
        b = self._update_btn
        b.configure(text=f"\u2302  Update to v{latest}", command=lambda: self._ask_update(latest))
        b.pack(side="right", padx=(0, 12))

    def _ask_update(self, latest):
        if messagebox.askyesno(
                "Update available",
                f"A newer RoadMind is out (v{latest}, you have {__version__}).\n\n"
                f"{self._update_notes}\n\n"
                "Open the download page for the new build?"):
            updater.open_release(self._update_url or
                                 "https://github.com/mohammedahakimmk-beep/roadmind/releases")

    # ---------------- window picking ----------------
    def _refresh_windows(self):
        self.win_combo.configure(state="normal")
        wins = capture.list_game_windows()
        self._wins = wins
        labels = [w["owner"] + (f" - {w['name']}" if w["name"] else "") for w in wins]
        self.win_combo.configure(state="readonly")
        self.win_combo["values"] = labels
        if labels:
            self.win_combo.current(0)
        self.btn_arm.configure(state="normal" if labels else "disabled")

    def _on_pick_window(self, ev=None):
        idx = self.win_combo.current()
        if idx < 0 or idx >= len(self._wins):
            return
        w = self._wins[idx]
        self.game_owner = w["owner"]
        self.game_pid = w.get("pid", 0)
        self.disarm()
        self.engine.stop()
        self.capture = capture.WindowCapture((w["x"], w["y"], w["w"], w["h"]))
        self.engine.start(self.capture)
        self.status.configure(
            text=f"Vision active on [{w['owner']}] \u00b7 "
                 f"screen={'ok' if sys_utils.is_screen_capture_allowed() else 'grants missing'} \u00b7 "
                 f"keyboard={'ok' if sys_utils.is_accessibility_trusted() else 'grants missing'}")

    # ---------------- autopilot ----------------
    def arm(self):
        if not self.capture:
            messagebox.showwarning("No target", "Pick a game window first.")
            return
        if sys_utils.requires_accessibility() and not sys_utils.is_accessibility_trusted():
            messagebox.showwarning(
                "Keyboard blocked \u2014 one fix",
                "RoadMind needs the Accessibility permission to send keyboard "
                "input. If the KEYBOARD status chip says OFF above, click it to "
                "open System Settings and:\n\n"
                "  1. find the app you launch RoadMind with (your terminal, or "
                "RoadMind.app for the .dmg)\n"
                "  2. switch it OFF, then ON again (macOS glitch)\n"
                "  3. quit that app completely and relaunch it\n\n"
                "The chips refresh by themselves \u2014 no restart needed.")
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
        self.btn_arm.configure(state="disabled", text="ARMED")
        self.controller.arm()
        self.status.configure(text=f"AUTOPILOT ARMED \u00b7 watching [{self.game_owner}]")

    def disarm(self):
        if self.armed:
            input_ctl.release_all()
        self.armed = False
        self.btn_arm.configure(state="normal", text="ARM AUTOPILOT")
        self.controller.disarm()
        self.status.configure(text="Autopilot paused \u2014 vision still running.")

    def _hard_stop(self):
        input_ctl.release_all()
        self.disarm()
        self.status.configure(text="STOP pressed \u2014 released all input")

    # ---------------- calibration ----------------
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
        messagebox.showinfo(
            "Calibration",
            "Fully-automatic probe: RoadMind will hold each whitelisted key briefly "
            "and measure latency + response with optical flow.\n\n"
            "Make sure the car is in a safe open spot and the game window keeps focus.")
        self.wiz = calibrate.CalibrationWizard(
            self.cfg, self.capture,
            on_step=self._cal_step,
            on_done=self._cal_done,
            on_error=lambda e: self.status.configure(text="calibration error: " + str(e)),
            on_progress=self._cal_progress)
        self.progress.pack(side="left", padx=(0, 10))
        self._progress_on = True
        self.wiz.run()

    def _cal_step(self, action, msg):
        self.status.configure(text=msg)

    def _cal_progress(self, frac):
        self.progress["value"] = int(frac * 100)
        self.progress.update_idletasks()

    def _cal_done(self, results):
        self.progress.pack_forget()
        self._progress_on = False
        self.status.configure(text="Calibration saved: " + ", ".join(
            f"{a}={c.latency_ms:.0f}ms" for a, c in results.items()))

    # ---------------- main loop ----------------
    def _drain_events(self):
        while True:
            try:
                ev = self._events.get_nowait()
            except queue.Empty:
                return
            if ev == "kill":
                self._hard_stop()
                self.status.configure(text="KILL SWITCH \u2014 released all input")

    def _refresh_perms(self):
        """Lightweight permission re-read (~4x/sec). Returns True when changed."""
        input_ok = sys_utils.is_accessibility_trusted()
        screen_ok = sys_utils.is_screen_capture_allowed()
        hotkey_ok = sys_utils.input_monitoring_allowed()
        vision_ok = self.engine.frame is not None
        cur = (input_ok, screen_ok, hotkey_ok, vision_ok)
        if cur != self._perm_cache:
            self._perm_cache = cur
            self.chips.refresh(input_ok, screen_ok, hotkey_ok, vision_ok)
            return True
        return False

    def _tick(self):
        self._drain_events()
        self._tick_no += 1
        if self._tick_no % 10 == 0:
            self._refresh_perms()
        st = self.engine.state
        if self.engine.frame is not None:
            self.view.set_frame(self.engine.frame, st)
            self.view._draw()
        if st is not None:
            self.mem.update_state(st, self.engine.mem, self.armed)

        if self.armed:
            now = time.time()
            focus_ok = (now - self._armed_at) < 2.5
            if not focus_ok and safety.game_window_lost_focus(self.game_owner):
                self.status.configure(text="Game lost focus \u2014 autopilot paused.")
                self.disarm()
            else:
                if focus_ok and (now - self._armed_at) < 1.2 and self.game_pid:
                    sys_utils.activate_pid(self.game_pid)
                if now - self._last_plan_t > 0.1:
                    allowed = {a for a in C.ACTIONS if self.cfg.allowed(a)}
                    if not ({"throttle", "steer_left", "steer_right"} & allowed):
                        self.status.configure(text="No steering/throttle whitelisted.")
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
        self.destroy()


def build_app() -> tuple["MainWindow", None]:
    win = MainWindow()
    return win, None