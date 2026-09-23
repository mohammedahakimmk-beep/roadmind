"""Configuration & telemetry panels (Tk)."""

from __future__ import annotations

import tkinter as tk

from .. import config as C
from .. import sys_utils

BG = "#10141c"
PANEL = "#151a24"
FG = "#e6eef8"
ACC = "#66ccff"


class WhitelistPanel(tk.LabelFrame):
    """Checklist of every car action; unchecked = blocked at the action gate."""

    def __init__(self, master, cfg: C.RoadMindConfig, on_change=None):
        super().__init__(master, text=" Whitelist — what the autopilot MAY use ",
                         bg=BG, fg=ACC, labelanchor="nw",
                         font=("Helvetica", 10, "bold"))
        self.cfg = cfg
        self.on_change = on_change or (lambda: None)
        self._checks = {}
        self._entries = {}
        for i, action in enumerate(C.ACTIONS):
            var = tk.BooleanVar(value=cfg.allowed(action))
            cb = tk.Checkbutton(
                self, text=C.ACTION_LABELS[action], variable=var, bg=BG, fg=FG,
                activebackground=BG, activeforeground=FG, selectcolor=PANEL,
                font=("Helvetica", 9),
                command=lambda a=action: self._toggle(a))
            cb.grid(row=i, column=0, sticky="w", padx=6, pady=1)
            self._checks[action] = var
            e = tk.Entry(self, width=8, justify="center", bg=PANEL, fg=FG,
                         insertbackground=FG, relief="flat")
            e.insert(0, cfg.profile.bindings.get(action, ""))
            e.bind("<KeyRelease>", lambda ev, a=action: self._bind(a, ev.widget.get()))
            e.grid(row=i, column=1, sticky="e", padx=(6, 10), ipady=1)
            self._entries[action] = e
        tk.Button(self, text="SAVE", command=self._save, bg="#1c2a3a", fg=FG,
                  relief="flat", activebackground="#24425e", activeforeground=FG)\
            .grid(row=len(C.ACTIONS), column=0, columnspan=2, pady=(6, 0), sticky="ew")

    def _toggle(self, action):
        self.cfg.profile.actions[action] = self._checks[action].get()
        self.on_change()

    def _bind(self, action, text):
        self.cfg.profile.bindings[action] = text.strip().lower()
        self.on_change()

    def _save(self):
        self.cfg.save()


class MemoryPanel(tk.LabelFrame):
    """Live telemetry + remembered world."""

    def __init__(self, master):
        super().__init__(master, text=" AI memory & telemetry ",
                         bg=BG, fg=ACC, labelanchor="nw",
                         font=("Helvetica", 10, "bold"))
        self._v = {}
        rows = [
            ("speed_limit", "SPEED LIMIT (remembered)"),
            ("light", "TRAFFIC LIGHT"),
            ("leader", "VEHICLE AHEAD"),
            ("tracks", "OBJECTS"),
            ("motion", "MOTION / SPEED"),
            ("fps", "BRAIN FPS"),
        ]
        for i, (key, label) in enumerate(rows):
            tk.Label(self, text=label, bg=BG, fg="#4d6c8c",
                     font=("Helvetica", 8, "bold"), anchor="w")\
                .grid(row=i, column=0, sticky="w", padx=8, pady=(4, 0))
            val = tk.Label(self, text="—", bg=BG, fg="#ffffff",
                           font=("Helvetica", 11, "bold"), anchor="w")
            val.grid(row=i, column=1, sticky="ew", padx=8, pady=(4, 0))
            self._v[key] = val
        self.grid_columnconfigure(1, weight=1)
        self._warn = tk.Label(self, text="", bg=BG, fg="#ff7777",
                              font=("Helvetica", 8), justify="left", anchor="w",
                              wraplength=220)
        self._warn.grid(row=len(rows), column=0, columnspan=2, sticky="ew",
                        padx=8, pady=(8, 4))
        self._armed_lbl = self._v

    def update_state(self, st, memory, armed: bool):
        if st is None:
            return
        lim = memory.speed_limit
        tail = "  (seen)" if memory.did_see_limit else ""
        self._v["speed_limit"].config(text=(str(lim) if lim else "—") + tail)
        self._v["light"].config(text=st.light_state if st.light_state else "unknown")
        self._v["leader"].config(
            text=(str(st.leader.get("label", "—")) + f" @ {st.leader_distance:.0%} close")
            if st.leader else "clear road")
        self._v["tracks"].config(text=f"{len(st.tracks)} objects")
        self._v["motion"].config(text=f"{st.motion:.3f} px/f  est {st.speed_est:.0%}")
        self._v["fps"].config(text=f"{st.fps:.0f} vision fps")
        msgs = []
        if not sys_utils.is_accessibility_trusted():
            msgs.append("ACCESSIBILITY not granted — input won't work")
        if not sys_utils.is_screen_capture_allowed():
            msgs.append("SCREEN RECORDING not granted — captures are black")
        if armed:
            msgs.append("AUTOPILOT ARMED — ctrl+alt+Q = instant stop")
        self._warn.config(text="\n".join(msgs))