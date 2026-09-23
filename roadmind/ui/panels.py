"""RoadMind right-hand panels + live status chips (Tk, themed)."""

from __future__ import annotations

import tkinter as tk

from .. import config as C
from .. import sys_utils
from . import theme as T

PERM_HINT = (
    "RoadMind needs two macOS permissions:\n"
    "\n"
    "  - Accessibility  -> required for keyboard control\n"
    "  - Screen Recording -> required to see the game\n"
    "  - Input Monitoring -> needed for the ctrl+alt+Q hotkey\n"
    "\n"
    "If a chip stays off after you approved it, macOS is glitching on the "
    "approval. Fix (applies to the app you use to launch RoadMind - your "
    "terminal, or RoadMind.app if you run the .dmg):\n"
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
        tk.Label(self, text="STATUS", bg=T.BG_DEEP, fg=T.FG_FAINT,
                 font=T.UI_SM_B).pack(side="left", padx=(2, 8))
        for key, text, pane in (
            ("screen", "SCREEN", "com.apple.preference.security?Privacy_ScreenCapture"),
            ("input", "KEYBOARD", "com.apple.preference.security?Privacy_Accessibility"),
            ("hotkey", "HOTKEY", "com.apple.preference.security?Privacy_ListenEvent"),
        ):
            b = tk.Button(self, font=T.UI_SM_B, padx=10, pady=4, relief="flat", bd=0,
                          cursor="pointinghand",
                          command=lambda p=pane: sys_utils.open_settings_pane(p))
            b.pack(side="left", padx=(0, 6))
            self._btns[key] = (b, text)
        self._vision = tk.Button(self, text="VISION: booting", font=T.UI_SM_B,
                                 padx=10, pady=4, relief="flat", bd=0,
                                 bg=T.PANEL2, fg=T.FG_DIM,
                                 activebackground=T.PANEL2, activeforeground=T.FG_DIM)
        self._vision.pack(side="left", padx=(0, 6))
        tk.Button(self, text="?", bg=T.BG_DEEP, fg=T.ACC2, relief="flat", bd=0,
                  font=T.UI_SM_B, cursor="pointinghand",
                  command=lambda: tk.messagebox.showinfo("Permissions help", PERM_HINT),
                  activebackground=T.BG_DEEP, activeforeground=T.ACC)\
            .pack(side="left")

    def refresh(self, input_ok: bool, screen_ok: bool, hotkey_ok: bool, vision_ok: bool):
        for key, ok in (("input", input_ok), ("screen", screen_ok),
                        ("hotkey", hotkey_ok)):
            b, text = self._btns[key]
            on = "ON" if ok else "OFF"
            b.configure(
                text=f"{text} {on}",
                bg=T.PANEL2 if ok else T.RED,
                fg=T.GREEN if ok else "#1a0c10",
                activebackground=T.PANEL2 if ok else T.RED,
                activeforeground=T.GREEN if ok else "#1a0c10")
        self._vision.configure(
            text="VISION: LIVE" if vision_ok else "VISION: no window",
            bg=T.PANEL2 if vision_ok else T.PANEL,
            fg=T.GREEN if vision_ok else T.FG_FAINT,
            activeforeground=T.GREEN if vision_ok else T.FG_FAINT)


class WhitelistPanel(tk.Frame):
    """Checklist of every car action; unchecked = blocked at the action gate."""

    def __init__(self, master, cfg: C.RoadMindConfig, on_change=None):
        super().__init__(master, bg=T.BG)
        self.cfg = cfg
        self.on_change = on_change or (lambda: None)
        head = T.label(self, "WHITELIST \u2014 what the autopilot MAY use",
                       font=T.UI_SM_B, fg=T.FG_FAINT, bg=T.BG)
        head.pack(fill="x", padx=10, pady=(8, 4))
        self._row = {}
        self._checks = {}
        self._entries = {}
        for i, action in enumerate(C.ACTIONS):
            row = T.frame(self, bg=T.BG)
            row.pack(fill="x", padx=8, pady=1)
            var = tk.BooleanVar(value=cfg.allowed(action))
            cb = tk.Checkbutton(
                row, text=C.ACTION_LABELS[action], variable=var,
                bg=T.BG, fg=T.FG, activebackground=T.BG, activeforeground=T.FG,
                selectcolor=T.PANEL2, highlightthickness=0,
                font=(T.UI[0], 9),
                cursor="pointinghand",
                command=lambda a=action: self._toggle(a))
            cb.pack(side="left", padx=(2, 6))
            kb = T.label(row, "KEY", font=T.UI_SM, fg=T.FG_FAINT, bg=T.BG)
            kb.pack(side="right", padx=(4, 4))
            e = T.entry(row, width=7, font=T.MONO_SM)
            e.insert(0, cfg.profile.bindings.get(action, ""))
            e.bind("<KeyRelease>", lambda ev, a=action: self._bind(a, ev.widget.get()))
            e.pack(side="right", padx=(0, 8), ipady=1)
            self._checks[action] = var
            self._entries[action] = e
        T.button(self, text="SAVE WHITELIST", command=self._save,
                 bg=T.PANEL2, active="#2e3b66", font=T.UI_B, padx=10, pady=6)\
            .pack(fill="x", padx=10, pady=(8, 10))

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
        T.label(self, "AI MEMORY & TELEMETRY", font=T.UI_SM_B, fg=T.FG_FAINT,
                bg=T.BG).pack(anchor="w", padx=10, pady=(8, 4))
        self._v = {}
        rows = [
            ("speed_limit", ("Feed"),),
            ("light", ("Feed"),),
            ("leader", ("Feed"),),
            ("tracks", ("Feed"),),
            ("motion", ("Feed"),),
            ("fps", ("Feed"),),
        ]
        card = T.frame(self, bg=T.PANEL, line=True)
        card.pack(fill="x", padx=10)
        rows = [
            ("speed_limit", "SPEED LIMIT", "(remembered)"),
            ("light", "TRAFFIC LIGHT", ""),
            ("leader", "VEHICLE AHEAD", ""),
            ("tracks", "OBJECTS", ""),
            ("motion", "MOTION / SPEED", ""),
            ("fps", "BRAIN FPS", ""),
        ]
        for i, (key, lbl, extra) in enumerate(rows):
            l = T.label(card, lbl + (" " + extra if extra else ""),
                        font=T.UI_SM, fg=T.FG_DIM, bg=T.PANEL)
            l.grid(row=i, column=0, sticky="w", padx=10, pady=(5, 0))
            v = T.label(card, "\u2014", font=T.MONO_B, bg=T.PANEL)
            v.grid(row=i, column=1, sticky="e", padx=10, pady=(5, 0))
            self._v[key] = v
        self._warn = T.label(card, "", font=T.UI_SM, fg=T.RED, bg=T.PANEL,
                             justify="left", wraplength=230)
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
            text=(f"{st.leader.get('label','?')} @{st.leader_distance:.0%}")
            if st.leader else "clear road")
        self._v["tracks"].configure(text=f"{len(st.tracks)} objects")
        self._v["motion"].configure(text=f"{st.motion:.3f}px  {st.speed_est:.0%}")
        self._v["fps"].configure(text=f"{st.fps:.0f} fps")
        msgs = []
        if armed:
            msgs.append("ARMED \u00b7 ctrl+alt+Q = instant stop")
        if not sys_utils.is_accessibility_trusted():
            msgs.append("KEYBOARD: Accessibility OFF \u2014 toggle it in the chip above")
        if not sys_utils.is_screen_capture_allowed():
            msgs.append("SCREEN: Screen Recording OFF \u2014 captures are black")
        self._warn.configure(text="\n".join(msgs))