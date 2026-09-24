"""RoadMind UI theme: a small design system for the Tk interface.

Tk has no CSS, so this module is the stylesheet: palette, fonts, rounded
"pill" buttons, rounded panels and widget factories. Everything the user
sees is themed here so the whole app stays coherent in one place.
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont

# ---- palette (high-contrast; every text colour is readable on its surface) ----
BG_DEEP   = "#07090f"   # window background
BG        = "#0b1020"   # main surfaces / panels
PANEL     = "#10192c"   # cards inside panels
PANEL2    = "#1b2647"   # buttons / inputs / slots
LINE      = "#2a3a66"   # hairline borders
FG        = "#eef3ff"   # primary text
FG_DIM    = "#a7b8db"   # secondary text
FG_FAINT  = "#859ac6"   # tertiary text (still readable on dark)
ACC       = "#4dd6ff"   # cyan accent (brand)
ACC2      = "#7a8cff"   # secondary accent
GREEN     = "#3ce9a0"
AMBER     = "#ffc14d"
RED       = "#ff5f6e"
GO_DARK   = "#071017"   # text on cyan / bright pills
GOOD_TEXT = "#06231a"   # text on green pills
WARN_TEXT = "#241800"   # text on amber pills
RED_TEXT  = "#1c0b0e"   # text on red pills

# gameplay viewport
VPORT_IN   = "#04060b"   # inside the gameplay bezel
VPORT_BEZEL = "#141d38"  # bezel ring around the gameplay

# ---- fonts (platform-aware: SF Pro on macOS, Segoe UI on Windows) ----
if sys.platform == "darwin":
    _FAM, _MONO = "SF Pro Text", "Menlo"
else:
    _FAM, _MONO = "Segoe UI", "Consolas"

UI      = (_FAM, 10)
UI_B    = (_FAM, 10, "bold")
UI_SM   = (_FAM, 8)
UI_SM_B = (_FAM, 8, "bold")
H       = (_FAM, 14, "bold")
BRAND   = (_FAM, 16, "bold")
MONO    = (_MONO, 10)
MONO_B  = (_MONO, 10, "bold")
MONO_SM = (_MONO, 8)

# ---- colour helpers --------------------------------------------------------
def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def mix(c1: str, c2: str, t: float) -> str:
    a, b = _rgb(c1), _rgb(c2)
    return _hex(tuple(a[i] * (1 - t) + b[i] * t for i in range(3)))


def lighten(c: str, f: float = 0.12) -> str:
    return mix(c, "#ffffff", f)


def darken(c: str, f: float = 0.18) -> str:
    return mix(c, "#01020a", f)


# ---- rounded drawing --------------------------------------------------------
def round_rect(c, x1, y1, x2, y2, r, **kw):
    """A smooth rounded rectangle drawn as a polygon (Tk has no native one)."""
    r = max(2, min(float(r), abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, splinesteps=24, **kw)


# ---- widgets ------------------------------------------------------------------
class PillButton(tk.Canvas):
    """Fully rounded (curved) button: canvas-drawn, with hover and press states."""

    def __init__(self, master, text="", command=None, bg=PANEL2, fg=FG,
                 hover=None, active=None, disabled_bg=PANEL, disabled_fg=FG_FAINT,
                 font=UI_B, padx=14, pady=7, radius=None):
        super().__init__(
            master,
            bg=master.cget("bg") if isinstance(master, tk.Widget) else BG_DEEP,
            highlightthickness=0, bd=0)
        self._text = str(text)
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover = hover or lighten(bg, 0.10)
        self._active = active or darken(bg, 0.18)
        self._d_dis = disabled_bg
        self._d_fg = disabled_fg
        self._font = font
        self._padx, self._pady = padx, pady
        self._radius = radius
        self._state = "normal"
        self._inside = False
        self._down = False
        self.configure(cursor="pointinghand")
        self.bind("<Enter>", lambda e: self._hover_in())
        self.bind("<Leave>", lambda e: self._hover_out())
        self.bind("<ButtonPress-1>", lambda e: self._press())
        self.bind("<ButtonRelease-1>", lambda e: self._release())
        self._redraw()

    # -- state --
    def _enabled(self):
        return self._state == "normal"

    def _cur_bg(self):
        if not self._enabled():
            return self._d_dis
        if self._down and self._inside:
            return self._active
        if self._inside:
            return self._hover
        return self._bg

    # -- drawing --
    def _redraw(self):
        f = tkfont.Font(family=self._font[0], size=self._font[1],
                        weight=self._font[2] if len(self._font) > 2 else "normal")
        tw = f.measure(self._text)
        th = f.metrics("linespace")
        w = max(6, tw + 2 * self._padx + 6)
        h = max(6, th + 2 * self._pady + 4)
        if self._radius:
            h = max(h, self._radius * 2)
        self.configure(width=w, height=h)
        self.delete("all")
        r = self._radius or (h // 2)
        col = self._cur_bg()
        round_rect(self, 1, 1, w - 1, h - 1, r, fill=col, outline=col)
        tcol = self._fg if self._enabled() else self._d_fg
        self.create_text(w / 2, h / 2, text=self._text, fill=tcol, font=self._font)

    # -- events --
    def _hover_in(self):
        self._inside = True
        self._redraw()

    def _hover_out(self):
        self._inside = False
        self._down = False
        self._redraw()

    def _press(self):
        self._down = True
        self._redraw()

    def _release(self):
        was, self._down = self._down, False
        self._redraw()
        if was and self._inside and self._enabled() and self._command:
            self._command()

    # -- API --
    def configure(self, **kw):
        changed = False
        if "text" in kw:
            self._text = str(kw.pop("text"))
            changed = True
        if "command" in kw:
            self._command = kw.pop("command")
        if "bg" in kw:
            self._bg = kw.pop("bg")
            self._hover = lighten(self._bg, 0.10)
            self._active = darken(self._bg, 0.18)
            changed = True
        if "fg" in kw:
            self._fg = kw.pop("fg")
            changed = True
        if "hover" in kw:
            self._hover = kw.pop("hover")
        if "active" in kw:
            self._active = kw.pop("active")
        if "font" in kw:
            self._font = kw.pop("font")
            changed = True
        if "state" in kw:
            st = kw.pop("state")
            self._state = "disabled" if st in ("disabled", "") else "normal"
            super().configure(cursor="arrow" if self._state == "disabled" else "pointinghand")
            changed = True
        if kw:
            super().configure(kw)
        if changed:
            self._redraw()


class RoundedPanel(tk.Canvas):
    """A rounded bezel "box": outer ring + darker interior. Pack child widgets
    with pad >= self.pad and a background equal to `interior`; their square
    corners then sit on the interior colour and read as rounded."""

    def __init__(self, master, radius=16, bezel=VPORT_BEZEL, interior=VPORT_IN,
                 outside=BG_DEEP, line=LINE):
        super().__init__(master, bg=outside, highlightthickness=0, bd=0)
        self.radius = radius
        self.pad = radius + 6
        self._bezel, self._interior, self._line = bezel, interior, line
        self.bind("<Configure>", lambda e: self._paint())
        self._paint()

    def _paint(self, _e=None):
        w = max(4, self.winfo_width())
        h = max(4, self.winfo_height())
        self.delete("all")
        r = max(4, min(self.radius, (w - 2) // 2, (h - 2) // 2))
        round_rect(self, 1, 1, w - 1, h - 1, r,
                   fill=self._bezel, outline=self._line, width=1)
        if r > 3:
            round_rect(self, 3, 3, w - 4, h - 4, max(3, r - 3),
                       fill=self._interior, outline=self._interior)


# ---- simple factories --------------------------------------------------------
def frame(master, bg=BG, line=False, padx=0, pady=0, **kw):
    kw.setdefault("bg", bg)
    if line:
        kw.setdefault("highlightbackground", LINE)
        kw.setdefault("highlightthickness", 1)
    return tk.Frame(master, **kw)


def label(master, text="", fg=FG, font=UI, bg=PANEL, **kw):
    kw.setdefault("anchor", "w")
    return tk.Label(master, text=text, fg=fg, bg=bg, font=font, **kw)


def button(master, text, command=None, bg=PANEL2, fg=FG, font=UI_B,
           active=None, hover=None, padx=14, pady=7, radius=None, **kw):
    return PillButton(master, text, command=command, bg=bg, fg=fg,
                      active=active, hover=hover, font=font,
                      padx=padx, pady=pady, radius=radius)


def pill(master, text, command=None, bg=PANEL2, fg=FG, font=UI_SM_B,
         active=None, hover=None, padx=8, pady=3, radius=None, **kw):
    return PillButton(master, text, command=command, bg=bg, fg=fg,
                      active=active, hover=hover, font=font,
                      padx=padx, pady=pady, radius=radius)


def entry(master, width=10, bg=PANEL2, fg=FG, font=UI, **kw):
    return tk.Entry(master, width=width, bg=bg, fg=fg, insertbackground=fg,
                    relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=LINE, highlightcolor=ACC,
                    font=font, **kw)


def chip(master, text, command=None, on=False, color=GREEN, dim=False):
    bg = PANEL if on else PANEL2
    fg = GOOD_TEXT if on and color == GREEN else (FG if on else FG_FAINT)
    b = pill(master, text, command=command, bg=bg, fg=fg,
             active=darken(bg, 0.2), hover=lighten(bg, 0.1))
    return (b, on, color)