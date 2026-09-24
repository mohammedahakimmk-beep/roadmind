"""GameROBOT dashboard: the game-menu / launcher scene.

A full-bleed animated menu (drifting particles, glow title, rotating taglines)
with the essentials: who you are (WELCOME BACK, DRIVER), the running version,
target-game picker, a permissions strip, a settings card (vision overlays +
speed targets) and the big IGNITE ENGINE button that drops you into the cockpit.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import ttk

from .. import sys_utils, __version__
from . import theme as T

TAGLINES = [
    "READY TO HIT THE ROAD?",
    "YOUR CO-PILOT IS ONLINE.",
    "CARS, PEOPLE, SIGNS \u2014 ALL UNDERSTOOD.",
    "NO CLOUD. NO TEACHING. FULLY LOCAL.",
    "IT SEES. IT THINKS. IT DRIVES YOU.",
]

EYEBROW = "AI AUTOPILOT FOR DRIVING GAMES"
SUB = ("Sees drivers & people, reads speed-limit signs, tracks every object \u00b7 "
       "and only touches the controls you whitelist.")


class DashboardScene(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG_DEEP)
        self.app = app
        self.cfg = app.cfg
        self.canvas = tk.Canvas(self, bg=T.BG_DEEP, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._layout())

        # particles
        self._particles = []
        self._sweep = {"on": 0.0, "x": -100.0}

        self._win_combo = None
        self._status_txt = None
        self._perm_btns = {}
        self._toggles = {}
        self._update_pill = None
        self._ignite = None
        self._ignite_sub = None
        self._title_id = None
        self._tagline_id = None

        self._build()
        self._schedule_anim()

    # ------------------------------------------------------------------ widgets
    def _build(self):
        c = self.canvas

        # IGNITE ENGINE: the fun main action (replaces a boring START)
        self._ignite = T.button(
            self, "\u25b6  IGNITE ENGINE", command=self.app.launch,
            bg=T.ACC, fg=T.GO_DARK, font=(T._FAM, 16, "bold"),
            padx=46, pady=16, radius=32)
        self._ignite.place(relx=0.5, rely=0.885, anchor="center")
        self._ignite.set_pulse(True, T.ACC2)
        T.label(self, "ENTER THE COCKPIT \u00b7 this is where the bot starts driving",
                bg=T.BG_DEEP, fg=T.FG_FAINT, font=T.UI_SM)\
            .place(relx=0.5, rely=0.942, anchor="center")

        # target game picker
        self._win_combo = ttk.Combobox(
            self, width=34, state="readonly", font=T.UI, foreground=T.FG)
        self._win_combo.place(relx=0.5, rely=0.455, anchor="center")
        self._win_combo.bind("<<ComboboxSelected>>", self._on_pick)
        T.pill(self, "\u21bb", command=self.app.refresh_games, bg=T.PANEL2,
               fg=T.FG, padx=10, pady=5, font=T.UI_B)\
            .place(relx=0.5, rely=0.455, anchor="center", x=230)

        # game status line under the picker
        self._status = T.label(self, "Pick a window and hit IGNITE ENGINE.",
                               bg=T.BG_DEEP, fg=T.FG_DIM, font=T.UI_SM)
        self._status.place(relx=0.5, rely=0.505, anchor="center")

        # permissions strip (mini pills: GAME + the three macOS-style toggles)
        for i, key in enumerate(("game", "screen", "input", "hotkey")):
            b = T.pill(self, f"{key.upper()} ...", bg=T.PANEL2, fg=T.FG_FAINT,
                       padx=9, pady=3, font=T.UI_SM_B,
                       command=(lambda k=key: self._open_perm_pane(k))
                       if key != "game" else None)
            b.place(relx=0.5, rely=0.545, anchor="center",
                    x=(i - 1.5) * 132)
            self._perm_btns[key] = b

        # settings card
        self._settings_row(0.665, 0.735)
        self._speed_row()

    def _settings_row(self, rely_top, rely_bot):
        labels = [("show_boxes", "BOXES"), ("show_speed", "EST SPEED"),
                  ("show_lanes", "LANES"), ("show_hud", "HUD")]
        y = (rely_top + rely_bot) / 2
        for i, (key, lbl) in enumerate(labels):
            on = bool(self.cfg.profile.ui.get(key, True))
            b = T.pill(self, lbl, command=lambda k=key: self._toggle(k),
                       bg=T.GREEN if on else T.PANEL2,
                       fg=T.GOOD_TEXT if on else T.FG_FAINT,
                       padx=12, pady=5, font=T.UI_SM_B)
            b.place(relx=0.5, rely=y, anchor="center", x=(i - 1.5) * 108)
            self._toggles[key] = b

    def _speed_row(self):
        def _mk(label, key, x):
            T.label(self, label, bg=T.BG_DEEP, fg=T.FG_DIM, font=T.UI_SM)\
                .place(relx=0.5, rely=0.795, anchor="center", x=x)
            e = T.entry(self, width=6, font=T.MONO)
            e.insert(0, str(int(self.cfg.profile.limits.get(key, 50))))
            e.bind("<Return>", lambda ev, k=key, e=e: self._save_limit(k, e.get()))
            e.place(relx=0.5, rely=0.795, anchor="center", x=x + 74)
            return e
        _mk("TARGET SPEED", "target_speed", -150)
        _mk("MAX SPEED", "max_speed", 40)

    # ------------------------------------------------------------ interactions
    def _toggle(self, key):
        self.cfg.profile.ui[key] = not bool(self.cfg.profile.ui.get(key, True))
        self.cfg.save()
        on = self.cfg.profile.ui[key]
        b = self._toggles[key]
        b.configure(bg=T.GREEN if on else T.PANEL2,
                    fg=T.GOOD_TEXT if on else T.FG_FAINT)

    def _save_limit(self, key, text):
        try:
            v = max(1, min(400, int(float(text))))
        except Exception:
            return
        self.cfg.profile.limits[key] = float(v)
        self.cfg.save()

    def _on_pick(self, _ev=None):
        self.app.pick_game_at(self._win_combo.current())

    def _open_perm_pane(self, key):
        pane = {"screen": "Privacy_ScreenCapture",
                "input": "Privacy_Accessibility",
                "hotkey": "Privacy_ListenEvent", }[key]
        sys_utils.open_settings_pane(pane)

    # -------------------------------------------------------------- data feeds
    def set_windows(self, labels):
        self._win_combo["values"] = labels
        if labels:
            self._win_combo.current(0)
        self._perm_btns["game"].configure(text=f"GAME: {len(labels)} FOUND" if labels
                                          else "GAME: NONE", bg=T.GREEN if labels
                                          else T.RED,
                                          fg=T.GOOD_TEXT if labels else "#ffd8dc")

    def set_perms(self, input_ok, screen_ok, hotkey_ok):
        for key, ok in (("input", input_ok), ("screen", screen_ok),
                        ("hotkey", hotkey_ok)):
            b = self._perm_btns.get(key)
            if not b:
                continue
            b.configure(text=f"{key.upper()} ON" if ok else f"{key.upper()} OFF",
                        bg=T.GREEN if ok else T.RED,
                        fg=T.GOOD_TEXT if ok else "#ffd8dc")

    def set_status(self, text):
        if self._status and text:
            self._status.configure(text=text)

    def set_update(self, latest):
        """Flash the version pill with the newer version when found."""
        pass  # reserved; cockpit still surfaces updates

    # ------------------------------------------------------------------ canvas
    def _layout(self, _ev=None):
        c = self.canvas
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        c.delete("scene")
        # base gradient
        T.draw_gradient(c, 0, 0, W, H, "#0a1120", "#05070d", 40)
        # soft glows behind the title
        cx, cy = W // 2, int(H * 0.16)
        for r, col in ((150, "#123254"), (90, "#0e2a4d"), (46, "#113a63")):
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline="",
                          tags="scene")
        # floor horizon glow (subtle road feel)
        c.create_line(0, int(H * 0.62), W, int(H * 0.62),
                      fill="#0c1526", width=1, tags="scene")
        # eyebrow + title + tagline + subtitle
        c.create_text(cx, int(H * 0.095), text=EYEBROW, fill=T.ACC2,
                      font=(T._FAM, 10, "bold"), tags="scene")
        c.create_text(cx, int(H * 0.145), text="WELCOME BACK, DRIVER",
                      fill=T.FG_FAINT, font=(T._FAM, 9), tags="scene")
        # glowing GameROBOT title (two-pass: soft halo + crisp face)
        c.create_text(cx + 2, int(H * 0.19) + 2, text="GameROBOT",
                      fill="#0d1b30", font=(T._FAM, 44, "bold"), tags="scene")
        self._title_id = c.create_text(cx, int(H * 0.19), text="GameROBOT",
                                       fill=T.ACC, font=(T._FAM, 44, "bold"),
                                       tags="scene")
        self._tagline_id = c.create_text(cx, int(H * 0.245), text=TAGLINES[0],
                                         fill="#7ecfff", font=(T._FAM, 10, "bold"),
                                         tags="scene")
        c.create_text(cx, int(H * 0.285), text=SUB, fill=T.FG_DIM,
                      font=(T._FAM, 9), tags="scene")
        # version pill (drawn, static)
        self._draw_version_pill(c, W, H)
        # motif: target label above the picker
        c.create_text(cx, int(H * 0.42), text="CHOOSE THE GAME YOU WANT ME TO DRIVE",
                      fill=T.FG_FAINT, font=(T._FAM, 8, "bold"), tags="scene")
        c.create_text(cx, int(H * 0.63), text="VISION OVERLAYS \u2014 WHAT THE BOT SHOWS YOU",
                      fill=T.FG_FAINT, font=(T._FAM, 8, "bold"), tags="scene")
        c.create_text(cx, int(H * 0.775), text="SPEED TARGETS (KM/H)",
                      fill=T.FG_FAINT, font=(T._FAM, 8, "bold"), tags="scene")

    def _draw_version_pill(self, c, W, H):
        text = f"v{__version__}  \u00b7  WINDOWS EDITION  \u00b7  opensource"
        f = (T._MONO, 9, "bold")
        w = max(120, int(len(text) * 7) + 26)
        h = 22
        x, y = W // 2 - w // 2, int(H * 0.335) - h // 2
        T.round_rect(c, x, y, x + w, y + h, h // 2, fill="#0e1830",
                     outline=T.LINE, width=1, tags="scene")
        c.create_text(W // 2, y + h // 2, text=text, fill=T.FG,
                      font=f, tags="scene")

    # ------------------------------------------------------------------ anims
    def _schedule_anim(self):
        self._anim_id = self.after(45, self._anm)

    def _anm(self):
        try:
            self.winfo_exists()
        except tk.TclError:
            return
        c = self.canvas
        W = c.winfo_width() or 100
        H = c.winfo_height() or 100
        now = __import__("time").time()

        # spawn / drift particles
        if len(self._particles) < 26 and random.random() < 0.3:
            self._particles.append(
                [random.uniform(0, W), random.uniform(0, H),
                 random.uniform(0.4, 1.4), random.uniform(0.2, 1.0)])
        for p in self._particles[:]:
            p[0] += p[3]
            p[1] -= p[2] * 0.35
            if p[1] < -6 or p[0] > W + 6:
                self._particles.remove(p)
        c.delete("dust")
        for x, y, sp, s in self._particles:
            col = T.mix("#4dd6ff", "#0a1120", 1.0 - s)
            c.create_rectangle(x, y, x + max(1.0, s * 2), y + max(1.0, s * 2),
                               fill=col, outline="", tags="dust")

        # rotating tagline
        if self._tagline_id:
            idx = int(now // 3.4) % len(TAGLINES)
            a = T.pulse_alpha(now, lo=0.55, hi=1.0)
            c.itemconfigure(self._tagline_id,
                            text=TAGLINES[idx],
                            fill=T.mix("#7ecfff", "#05070d", 1.0 - a))

        # title glow breathing
        if self._title_id:
            a = T.pulse_alpha(now * 0.8, lo=0.85, hi=1.0)
            c.itemconfigure(self._title_id,
                            fill=T.mix(T.ACC, "#11234a", 1.0 - a))

        # occasional light sweep across the whole menu
        self._sweep["x"] += 14
        if self._sweep["x"] > W + 320:
            self._sweep["x"] = -320
        sx = self._sweep["x"]
        mid = min(255, max(0, int(40 * (0.5 + 0.5 * math.sin(now * 0.9)))))
        band = f"#{mid:02x}{min(255, mid + 60):02x}ff"
        c.create_polygon(sx, 0, sx + 26, 0, sx - 160, H, sx - 186, H,
                         fill=band, stipple="gray25", outline="", tags="dust")

        self._anim_id = self.after(45, self._anm)

    def stop(self):
        if getattr(self, "_anim_id", None):
            try:
                self.after_cancel(self._anim_id)
            except tk.TclError:
                pass
            self._anim_id = None