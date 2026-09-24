"""RoadMind right-hand panels + live status chips (Tk, themed)."""

from __future__ import annotations

import tkinter as tk

from .. import config as C
from .. import sys_utils
from . import theme as T

PERM_HINT = (
    "What RoadMind needs:\n"
    "\n"
    "  Windows:\n"
    "    - nothing at all. No permissions, no admin, no install.\n"
    "\n"
    "  macOS (dev only - the DMG is discontinued):\n"
    "    - Accessibility   -> required for keyboard control\n"
    "    - Screen Recording -> required to see the game\n"
    "    - Input Monitoring -> needed for the ctrl+alt+Q hotkey\n"
    "\n"
    "If a macOS chip stays off after you approved it, macOS is glitching on "
    "the approval. Fix (applies to the app you launch RoadMind with - your "
    "terminal, or RoadMind.app):\n"
    "\n"
    "1. System Settings -> Privacy & Security -> the permission name\n"
    "2. Switch the app OFF, wait, switch it back ON\n"
    "3. Quit that app completely and relaunch it\n"
    "4. Start RoadMind again - the chips flip green\n"
)


class StatusChips(tk.Frame):
    """Live permission + vision indicator. Refreshes itself from sys_utils on demand."""

    def __init__(self, master):
        super().__init__(master, bg=T.BG_DEEP)
        self._btns = {}
        self._build()

    def _build(self):
        tk.Label(self, text="STATUS", bg=T.BG_DEEP, fg=T.FG_DIM,
                 font=T.UI_SM_B).pack(side="left", padx=(2, 10))
        for key, text, pane in (
            ("screen", "SCREEN", "com.apple.preference.security?Privacy_ScreenCapture"),
            ("input", "KEYBOARD", "com.apple.preference.security?Privacy_Accessibility"),
            ("hotkey", "HOTKEY", "com.apple.preference.security?Privacy_ListenEvent"),
        ):
            b = T.pill(self, f"{text} ...", bg=T.PANEL2, fg=T.FG_FAINT, padx=10, pady=4,
                       command=lambda p=pane: sys_utils.open_settings_pane(p))
            b.pack(side="left", padx=(0, 8))
            self._btns[key] = (b, text)
        self._vision = T.pill(self, "VISION: booting", bg=T.PANEL2, fg=T.FG_DIM,
                              padx=10, pady=4, command=None)
        self._vision.pack(side="left", padx=(0, 8))
        T.pill(self, "?", bg=T.BG_DEEP, fg=T.ACC2, padx=6, pady=4,
               hover=T.lighten(T.BG_DEEP, 0.06), command=lambda: tk.messagebox.showinfo(
                   "Permissions help", PERM_HINT)).pack(side="left")

    def refresh(self, input_ok: bool, screen_ok: bool, hotkey_ok: bool, vision_ok: bool):
        for key, ok in (("input", input_ok), ("screen", screen_ok),
                        ("hotkey", hotkey_ok)):
            b, text = self._btns[key]
            if ok:
                b.configure(text=f"{text} ON", bg=T.GREEN, fg=T.GOOD_TEXT)
            else:
                b.configure(text=f"{text} OFF", bg=T.RED, fg="#ffd8dc")
        if vision_ok:
            self._vision.configure(text="VISION: LIVE", bg=T.PANEL2, fg=T.GREEN)
        else:
            self._vision.configure(text="VISION: no window", bg=T.PANEL, fg=T.FG_FAINT)


class WhitelistPanel(tk.Frame):
    """Scrollable checklist of every car action; unchecked = blocked."""

    def __init__(self, master, cfg: C.RoadMindConfig, on_change=None):
        super().__init__(master, bg=T.BG)
        self.cfg = cfg
        self.on_change = on_change or (lambda: None)
        T.label(self, "WHITELIST \u2014 what the autopilot MAY use",
                font=T.UI_SM_B, fg=T.FG_DIM, bg=T.BG).pack(
                    fill="x", padx=12, pady=(10, 4))
        self._row = {}
        self._checks = {}
        self._entries = {}

        sc = tk.Canvas(self, bg=T.BG, highlightthickness=0, bd=0)
        bar = tk.Scrollbar(self, orient="vertical", command=sc.yview,
                           bg=T.BG_DEEP, troughcolor=T.BG_DEEP,
                           activebackground=T.PANEL2, highlightthickness=0)
        inner = tk.Frame(sc, bg=T.BG)
        sc.create_window((0, 0), window=inner, anchor="nw")
        sc.configure(yscrollcommand=bar.set)

        def _sync(_e=None):
            sc.configure(scrollregion=sc.bbox("all"))

        inner.bind("<Configure>", _sync)

        def _wheel(e):
            delta = -1 if e.delta > 0 else 1
            if hasattr(e, "delta") and abs(e.delta) > abs(e.num or 0):
                delta = -int(e.delta / 120) if e.delta else delta
            sc.yview_scroll(delta * 3, "units")

        for wgt in (sc, inner):
            wgt.bind("<MouseWheel>", _wheel, add="+")
            try:
                wgt.bind("<Button-4>", lambda e: sc.yview_scroll(-3, "units"), add="+")
                wgt.bind("<Button-5>", lambda e: sc.yview_scroll(3, "units"), add="+")
            except Exception:
                pass

        for i, action in enumerate(C.ACTIONS):
            row = T.frame(inner, bg=T.BG)
            row.pack(fill="x", padx=10, pady=1)
            var = tk.BooleanVar(value=cfg.allowed(action))
            cb = tk.Checkbutton(
                row, text=C.ACTION_LABELS[action], variable=var,
                bg=T.BG, fg=T.FG, activebackground=T.BG, activeforeground=T.FG,
                selectcolor=T.PANEL2, highlightthickness=0,
                font=(T.UI[0], 10),
                cursor="pointinghand",
                command=lambda a=action: self._toggle(a))
            cb.pack(side="left", padx=(2, 6))
            T.label(row, "KEY", font=T.UI_SM, fg=T.FG_FAINT, bg=T.BG)\
                .pack(side="right", padx=(4, 4))
            e = T.entry(row, width=7, font=T.MONO_SM)
            e.insert(0, cfg.profile.bindings.get(action, ""))
            e.bind("<KeyRelease>", lambda ev, a=action: self._bind(a, ev.widget.get()))
            e.pack(side="right", padx=(0, 8), ipady=1)
            self._checks[action] = var
            self._entries[action] = e

        bar.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)

        T.button(self, text="SAVE WHITELIST", command=self._save,
                 bg=T.PANEL2, active=T.darken(T.PANEL2, 0.2),
                 font=T.UI_B, padx=10, pady=8)\
            .pack(fill="x", padx=12, pady=(8, 12))

    def _toggle(self, action):
        self.cfg.profile.actions[action] = self._checks[action].get()
        self.on_change()

    def _bind(self, action, text):
        self.cfg.profile.bindings[action] = text.strip().lower()
        self.on_change()

    def _save(self):
        self.cfg.save()


class MemoryPanel(tk.Frame):
    """Live telemetry + remembered world."""

    def __init__(self, master):
        super().__init__(master, bg=T.BG)
        T.label(self, "AI MEMORY & TELEMETRY", font=T.UI_SM_B, fg=T.FG_DIM,
                bg=T.BG).pack(anchor="w", padx=12, pady=(10, 4))
        card = T.frame(self, bg=T.PANEL, line=True)
        card.pack(fill="x", padx=12)
        self._v = {}
        rows = [
            ("speed_limit", "SPEED LIMIT", "(remembered)"),
            ("light", "TRAFFIC LIGHT", ""),
            ("leader", "VEHICLE AHEAD", ""),
            ("tracks", "OBJECTS", ""),
            ("motion", "MOTION / SPEED", ""),
            ("fps", "BRAIN FPS", ""),
        ]
        for i, (key, lbl, extra) in enumerate(rows):
            T.label(card, lbl + (" " + extra if extra else ""),
                    font=T.UI_SM, fg=T.FG_DIM, bg=T.PANEL)\
                .grid(row=i, column=0, sticky="w", padx=10, pady=(5, 0))
            v = T.label(card, "\u2014", font=T.MONO_B, fg=T.FG, bg=T.PANEL)
            v.grid(row=i, column=1, sticky="e", padx=10, pady=(5, 0))
            self._v[key] = v
        self._warn = T.label(card, "", font=T.UI_SM, fg=T.AMBER, bg=T.PANEL,
                             justify="left", wraplength=250)
        self._warn.grid(row=len(rows), column=0, columnspan=2, sticky="ew",
                        padx=10, pady=(8, 6))

    def update_state(self, st, memory, armed: bool):
        if st is None:
            return
        lim = memory.speed_limit
        tail = " seen" if memory.did_see_limit else ""
        self._v["speed_limit"].configure(text=(str(lim) if lim else "\u2014") + tail)
        self._v["light"].configure(text=st.light_state or "unknown")
        self._v["leader"].configure(
            text=(f"{st.leader.get('label', '?')} @{st.leader_distance:.0%}")
            if st.leader else "clear road")
        self._v["tracks"].configure(text=f"{len(st.tracks)} objects")
        self._v["motion"].configure(text=f"{st.motion:.3f}px  {st.speed_est:.0%}")
        self._v["fps"].configure(text=f"{st.fps:.0f} fps")
        msgs = []
        if armed:
            msgs.append("ARMED \u00b7 ctrl+alt+Q = instant stop")
        if sys_utils.requires_accessibility() and not sys_utils.is_accessibility_trusted():
            msgs.append("KEYBOARD: Accessibility OFF \u2014 toggle it in the chip above")
        if sys_utils.requires_accessibility() and not sys_utils.is_screen_capture_allowed():
            msgs.append("SCREEN: Screen Recording OFF \u2014 captures are black")
        self._warn.configure(text="\n".join(msgs))