"""RoadMind UI theme: a small design system for the Tk interface.

Tk has no CSS, so this module is the stylesheet: palette, fonts, and
widget factories used across every panel. Keeps the whole app visually
coherent and easy to reshape in one place.
"""

from __future__ import annotations

import tkinter as tk

# ---- palette -----------------------------------------------------------
BG_DEEP = "#07090f"   # window background
BG      = "#0b1020"   # main surfaces / panels
PANEL   = "#0f1526"   # cards inside panels
PANEL2  = "#182040"   # buttons, inputs, accents-backgrounds
LINE    = "#232e52"   # hairline borders
FG      = "#e8eefb"   # primary text
FG_DIM  = "#94a7c9"   # secondary text
FG_FAINT = "#5a6a90"  # tertiary text
ACC     = "#4dd6ff"   # cyan accent (brand)
ACC2    = "#7a8cff"   # secondary accent
GREEN   = "#36e08a"
AMBER   = "#ffb63c"
RED     = "#ff5a6a"

# ---- fonts --------------------------------------------------------------
UI    = ("SF Pro Text", 10)          # falls back to Helvetica Neue if absent
UI_B  = ("SF Pro Text", 10, "bold")
UI_SM = ("SF Pro Text", 8)
UI_SM_B = ("SF Pro Text", 8, "bold")
H     = ("SF Pro Text", 13, "bold")
MONO  = ("Menlo", 10)
MONO_B = ("Menlo", 10, "bold")
MONO_SM = ("Menlo", 8)

# ---- widget factories -----------------------------------------------------
def frame(master, bg=BG, line=False, padx=0, pady=0, **kw) -> tk.Frame:
    kw.setdefault("bg", bg)
    if line:
        kw.setdefault("highlightbackground", LINE)
        kw.setdefault("highlightthickness", 1)
    return tk.Frame(master, **kw)


def label(master, text="", fg=FG, font=UI, bg=PANEL, **kw):
    kw.setdefault("anchor", "w")
    return tk.Label(master, text=text, fg=fg, bg=bg, font=font, **kw)


def button(master, text, command=None, bg=PANEL2, fg=FG, font=UI_B,
           active="#2e3b66", padx=14, pady=7, hover=None, **kw):
    b = tk.Button(master, text=text, command=command, bg=bg, fg=fg,
                  activebackground=active, activeforeground=fg,
                  relief="flat", bd=0, highlightthickness=0,
                  font=font, padx=padx, pady=pady, cursor="pointinghand", **kw)
    if hover:
        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def entry(master, width=10, bg=PANEL2, fg=FG, font=UI, **kw):
    return tk.Entry(master, width=width, bg=bg, fg=fg, insertbackground=fg,
                    relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=LINE, highlightcolor=ACC,
                    font=font, **kw)


def chip(master, text, command=None, on=False, color=GREEN, dim=False):
    fg = color if on else FG_FAINT
    b = tk.Button(master, text=text, command=command, bg=dim and PANEL or PANEL2,
                  fg=fg, activebackground=PANEL, activeforeground=color,
                  relief="flat", bd=0, font=UI_SM_B, padx=10, pady=4,
                  cursor="pointinghand")
    return (b, on, color)