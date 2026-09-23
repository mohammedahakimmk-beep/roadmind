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
from .panels import MemoryPanel, WhitelistPanel
from .road_view import RoadView

BGC = "#0a0e14"
BTN = "#1c2a3a"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"RoadMind AI Autopilot - {__version__}")
        self.geometry("1280x800")
        self.configure(bg=BGC)

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

        self._build_ui()
        self.safety.start(on_kill=lambda: self._events.put("kill"))
        self._refresh_windows()
        self._start_update_check()
        self.after(40, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------
    def _build_ui(self):
        head = tk.Frame(self, bg=BGC)
        head.pack(fill="x")
        tk.Label(head, text="ROADMIND", bg=BGC, fg="#66ccff",
                 font=("Helvetica", 16, "bold")).pack(side="left")
        tk.Label(head, text="  game window:", bg=BGC, fg="#9bb3c8",
                 font=("Helvetica", 10)).pack(side="left", padx=(16, 4))
        self.win_combo = ttk.Combobox(head, width=42, state="readonly")
        self.win_combo.pack(side="left")
        self.win_combo.bind("<<ComboboxSelected>>", self._on_pick_window)
        tk.Button(head, text="R", command=self._refresh_windows, bg=BTN,
                  fg="#e6eef8", relief="flat", width=2).pack(side="left", padx=4)
        if not sys_utils.is_accessibility_trusted():
            tk.Button(head, text="Grant Accessibility",
                      command=sys_utils.open_accessibility_settings,
                      bg="#7a1f2b", fg="white", relief="flat")\
                .pack(side="left", padx=4)
        if not sys_utils.is_screen_capture_allowed():
            tk.Button(head, text="Grant Screen Recording",
                      command=sys_utils.open_permissions_settings,
                      bg="#7a1f2b", fg="white", relief="flat")\
                .pack(side="left", padx=4)
        tk.Label(head, text="ctrl+alt+Q = emergency stop", bg=BGC,
                 fg="#7fe8a3", font=("Helvetica", 9)).pack(side="right")
        self._update_btn = tk.Button(head, text="", bg="#225588", fg="white",
                                     relief="flat", state="disabled")
        self._update_url = ""

        body = tk.PanedWindow(self, orient="horizontal", bg=BGC, sashwidth=6, bd=0)
        body.pack(fill="both", expand=True, pady=(8, 6))
        self.view = RoadView(body)
        body.add(self.view, minsize=520)

        right = tk.Frame(body, bg=BGC)
        body.add(right, minsize=320)
        self.mem = MemoryPanel(right)
        self.mem.pack(fill="x", pady=(0, 6))
        self.whitelist = WhitelistPanel(right, self.cfg)
        self.whitelist.pack(fill="both", expand=True)

        bar = tk.Frame(self, bg=BGC)
        bar.pack(fill="x")
        self.btn_arm = tk.Button(bar, text="ARM AUTOPILOT", bg="#00aa66",
                                 fg="white", font=("Helvetica", 11, "bold"),
                                 relief="flat", padx=18, pady=8,
                                 activebackground="#00bb77",
                                 activeforeground="white", command=self.arm)
        self.btn_arm.pack(side="left")
        self.btn_disarm = tk.Button(bar, text="PAUSE", bg="#cc7700", fg="white",
                                    font=("Helvetica", 10, "bold"), relief="flat",
                                    padx=14, pady=8, command=self.disarm)
        self.btn_disarm.pack(side="left", padx=6)
        self.btn_stop = tk.Button(bar, text="STOP ALL INPUT", bg="#cc2222",
                                  fg="white", font=("Helvetica", 10, "bold"),
                                  relief="flat", padx=14, pady=8,
                                  command=self._hard_stop)
        self.btn_stop.pack(side="left", padx=6)
        self.btn_cal = tk.Button(bar, text="CALIBRATE", bg="#225588", fg="white",
                                 font=("Helvetica", 10, "bold"), relief="flat",
                                 padx=14, pady=8, command=self._launch_calibration)
        self.btn_cal.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(bar, length=140, mode="determinate")
        self._progress_on = False
        self.status = tk.Label(bar, text="Select your game window to start vision.",
                               bg=BGC, fg="#9bb3c8", font=("Helvetica", 9))
        self.status.pack(side="left", padx=14)
        tk.Label(bar, text=f"RoadMind {__version__} - open source",
                 bg=BGC, fg="#4b5b6e", font=("Helvetica", 8)).pack(side="right")

    # ---------------- updater ----------------
    def _start_update_check(self):
        self._updater = updater.Updater(on_result=self._on_update)
        self._updater.poll()

    def _on_update(self, latest, url, notes):
        self._update_url = url or ""
        self._update_notes = notes or ""
        btn = self._update_btn
        btn.config(text=f"  Update v{latest}  ", state="normal",
                   command=lambda: self._ask_update(latest))
        btn.pack(side="right", padx=(0, 6))

    def _ask_update(self, latest):
        if messagebox.askyesno(
                "Update available",
                f"A newer RoadMind is out (v{latest}, you have {__version__}).\n\n"
                f"{self._update_notes}\n\n"
                "Open the download page so you can update the DMG instead of reinstalling?"):
            updater.open_release(self._update_url or
                                 "https://github.com/mohammedahakimmk-beep/roadmind/releases")

    # ---------------- window picking ----------------
    def _refresh_windows(self):
        self.win_combo.config(state="normal")
        wins = capture.list_game_windows()
        self._wins = wins
        labels = [(w["owner"] + ((" - " + w["name"]) if w["name"] else "")) for w in wins]
        self.win_combo.config(state="readonly")
        self.win_combo["values"] = labels
        self.win_combo.current(0) if labels else None
        self.btn_arm.config(state="normal" if labels else "disabled")

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
        self.status.config(
            text=f"Vision active on [{w['owner']}] - "
                 f"screen={'ok' if sys_utils.is_screen_capture_allowed() else 'PROMPT'} "
                 f"input={'ok' if sys_utils.is_accessibility_trusted() else 'PROMPT'}")

    # ---------------- autopilot ----------------
    def arm(self):
        if not self.capture:
            messagebox.showwarning("No target", "Pick a game window first.")
            return
        if not sys_utils.is_accessibility_trusted():
            messagebox.showwarning(
                "Permission missing",
                "Accessibility permission is required for keyboard control.\n"
                "Grant it to the app running RoadMind, then restart RoadMind.")
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
        self.btn_arm.config(state="disabled", text="ARMED")
        self.controller.arm()
        self.status.config(text=f"AUTOPILOT ARMED - watching [{self.game_owner}]")

    def disarm(self):
        if self.armed:
            input_ctl.release_all()
        self.armed = False
        self.btn_arm.config(state="normal", text="ARM AUTOPILOT")
        self.controller.disarm()
        self.status.config(text="Autopilot paused - vision still running.")

    def _hard_stop(self):
        input_ctl.release_all()
        self.disarm()
        self.status.config(text="STOP pressed - released all input")

    # ---------------- calibration ----------------
    def _launch_calibration(self):
        if self.armed:
            self.disarm()
        if not self.capture:
            messagebox.showwarning("No target", "Select a game window first.")
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
            on_error=lambda e: self.status.config(text="calibration error: " + str(e)),
            on_progress=self._cal_progress)
        self.progress.pack(side="left", padx=(0, 10))
        self._progress_on = True
        self.wiz.run()

    def _cal_step(self, action, msg):
        self.status.config(text=msg)

    def _cal_progress(self, frac):
        self.progress["value"] = int(frac * 100)
        self.progress.update_idletasks()

    def _cal_done(self, results):
        self.progress.pack_forget()
        self._progress_on = False
        self.status.config(text="Calibration saved: " + ", ".join(
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
                self.status.config(text="KILL SWITCH - released all input")

    def _tick(self):
        self._drain_events()
        st = self.engine.state
        if self.engine.frame is not None:
            self.view.set_frame(self.engine.frame, st)
            self.view._draw()
        if st is not None:
            self.mem.update_state(st, self.engine.mem, self.armed)

        if self.armed:
            now = time.time()
            # short grace after arming so the game can take focus
            focus_ok = (now - self._armed_at) < 2.5
            if not focus_ok and safety.game_window_lost_focus(self.game_owner):
                self.status.config(text="Game lost focus - autopilot paused.")
                self.disarm()
            else:
                if focus_ok and (now - self._armed_at) < 1.2 and self.game_pid:
                    sys_utils.activate_pid(self.game_pid)
                if now - self._last_plan_t > 0.1:
                    allowed = {a for a in C.ACTIONS if self.cfg.allowed(a)}
                    if not ({"throttle", "steer_left", "steer_right"} & allowed):
                        self.status.config(text="No steering/throttle whitelisted.")
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