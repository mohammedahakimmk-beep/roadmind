"""GameROBOT Tesla-style live vision view using Tk Canvas.

The whole viewport is a rounded dark "bezel box"; inside we draw the dimmed
game frame, the projected road/lanes, every object the AI understands with a
bounding box and a label chip above it ("CAR · EST SPEED: 60"), the speed-limit
dial and the AI's current thinking. Adds a moving scan-line + pulsing live dot
so the view feels alive.
"""

from __future__ import annotations

import time
import tkinter as tk

from PIL import Image, ImageTk

from . import theme as T

# friendly display names for what the YOLO brain understands
DISPLAY = {
    "person": "HUMAN",
    "bicycle": "CYCLIST",
    "motorcycle": "MOTORCYCLE",
    "car": "CAR",
    "bus": "BUS",
    "truck": "TRUCK",
    "traffic_light": "TRAFFIC LIGHT",
    "stop_sign": "STOP SIGN",
}

# classes we give a boxed speed estimate (moving things, not signs/lights)
_SPEED_CLASSES = {0, 1, 2, 3, 5, 7}

_CLASS_COLOR = {
    0: "#4dffa0",     # person
    1: "#42d9ff",     # bicycle
    3: "#ffb648",     # motorcycle
    9: "#c0a5ff",     # traffic light
    11: "#ff5f6e",    # stop sign
}


def _bgra_to_rgb_bytes(frame):
    return frame[:, :, :3][:, :, ::-1].tobytes()


def _label(t: dict) -> str:
    return DISPLAY.get(t.get("label") or t.get("cls"), (t.get("label") or "?")).upper()


class RoadView(tk.Frame):
    def __init__(self, master, game_label="pick a game window", prefs=None):
        super().__init__(master, bg=T.VPORT_IN, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=T.VPORT_IN, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.frame = None
        self.state = None
        self.armed = False
        self.game_label = game_label
        self.prefs = prefs or {}
        self._photo = None

    def set_frame(self, frame, state):
        self.frame = frame
        self.state = state

    # -- helpers ------------------------------------------------------------
    def _p(self, k, d=True):
        return bool(self.prefs.get(k, d))

    # -- drawing ------------------------------------------------------------
    def _draw(self):
        c = self.canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return
        now = time.time()

        if self.frame is not None:
            self._blit_frame(c, W, H)

        st = self.state
        hz = int(H * 0.42)
        vpx = W / 2

        if st is not None and self._p("show_lanes") and st.lanes.get("valid"):
            off = st.lanes.get("offset", 0.0)
            ang = st.lanes.get("angle", 0.0)
            vpx = vpx + off * W * -0.5 + ang * W * 0.15
            lane = ("#50ceff", "#36d98a")
            c.create_line(int(W * 0.16), H, int(vpx - W * 0.06), hz,
                          fill=lane[0], width=2)
            c.create_line(int(W * 0.84), H, int(vpx + W * 0.06), hz,
                          fill=lane[0], width=2)
            c.create_line(int(W * 0.48), H, int(vpx), hz,
                          fill=lane[1], width=3, dash=(10, 8))

        if st is not None and st.tracks and self._p("show_boxes"):
            for t in st.tracks:
                cx = vpx + (t.x - 0.5) * W * 1.6
                cy = H * (0.62 + (t.y - 0.6) * 0.9)
                bw = int(max(20, min(W * 0.45, t.w * W * 3.2)))
                bh = int(max(20, min(H * 0.5, t.h * H * 1.6)))
                self._object_box(c, cx, cy, bw, bh, t, now)

        self._chrome(c, W, H, now)
        self._hud(c, W, H, hz, st, now)

        # sweep scan line (always animating above the road: it feels "live")
        sy = int((now * 0.35) % 1.0 * H)
        a = 0.10 + 0.05 * (0.5 + 0.5 * __import__("math").sin(now * 2.0))
        c.create_line(0, sy, W, sy, fill=T.mix(T.ACC, T.VPORT_IN, 1.0 - a), width=1)

    def _blit_frame(self, c, W, H):
        h, w = self.frame.shape[:2]
        img = Image.frombytes("RGB", (w, h), _bgra_to_rgb_bytes(self.frame))
        scale = max(W / w, H / h)
        nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
        img = img.resize((nw, nh), Image.BILINEAR)
        x0 = (nw - W) // 2
        y0 = (nh - H) // 2
        img = img.crop((x0, y0, x0 + W, y0 + H))
        img = img.point(lambda v: int(v * 0.6))
        self._photo = ImageTk.PhotoImage(img)
        c.create_image(0, 0, image=self._photo, anchor="nw")

    def _chrome(self, c, W, H, now):
        """The 'screen' frame: crisp border + live badge + object count."""
        c.create_rectangle(1, 1, W - 2, H - 2, outline=T.VPORT_BEZEL, width=1)
        live = self.frame is not None
        # top status strip
        c.create_rectangle(0, 0, W, 30, fill="#06090f", outline="")
        c.create_line(0, 30, W, 30, fill=T.VPORT_BEZEL, width=1)
        dot = T.GREEN if live else T.FG_FAINT
        if live:
            # pulsing live dot
            import math
            pr = 3 + int(2 * (0.5 + 0.5 * math.sin(now * 4.5)))
            c.create_oval(12 - pr, 24 - pr, 12 + pr, 24 + pr,
                          fill=T.mix(T.GREEN, T.VPORT_IN, 0.5),
                          outline="")
        c.create_oval(12, 20, 20, 28, fill=dot, outline=dot)
        c.create_text(26, 24, text="LIVE VISION" if live else "VISION STANDBY",
                      fill=(T.GREEN if live else T.FG_FAINT),
                      font=(T._FAM, 9, "bold"), anchor="w")
        right = ""
        if self.state is not None:
            n = len(self.state.tracks)
            right = f"{n} OBJ" if n else "ROAD CLEAR"
            if self.state.speed_limit:
                right += f" \u00b7 LIMIT {self.state.speed_limit}"
        mid = f"{self.game_label}  \u00b7  {right}"
        c.create_text(W / 2, 24, text=mid,
                      fill=T.FG_DIM, font=(T._FAM, 9), anchor="center")
        # bottom strip
        c.create_line(0, H - 22, W, H - 22, fill=T.VPORT_BEZEL, width=1)
        c.create_text(W - 12, H - 12, text="GameROBOT \u00b7 AI AUTOPILOT",
                      fill=T.FG_FAINT, font=(T._FAM, 8), anchor="e")

    def _object_box(self, c, cx, cy, bw, bh, t, now):
        """A bounding box + label chip above it for every object the AI sees."""
        x1, y1 = int(cx - bw / 2), int(cy - bh / 2)
        x2, y2 = int(cx + bw / 2), int(cy + bh / 2)
        col = _CLASS_COLOR.get(t.cls, "#ff9f2e")
        if t.cls in (2, 3, 5, 7):  # vehicles: colour by how close they are
            hf = t.h
            col = "#ff4d5e" if hf > 0.15 else ("#ff9f2e" if hf > 0.08 else "#ffce3a")

        # box
        c.create_rectangle(x1, y1, x2, y2, outline=col, width=2,
                           fill=self._fade(col))
        n = 5
        c.create_line(x1, y1 + n, x1, y1, x2, y1, x2, y1 + n,
                      fill=T.lighten(col, 0.25), width=3)
        c.create_line(x1, y2 - n, x1, y2, x2, y2, x2, y2 - n,
                      fill=T.lighten(col, 0.25), width=3)

        # label chip above the box
        disp = _label(t)
        speed = int(round(t.est_kmh)) if getattr(t, "moving", False) else None
        show_speed = self._p("show_speed") and speed is not None \
            and t.cls in _SPEED_CLASSES
        text = f"{disp} \u00b7 EST SPEED: {speed}" if show_speed else disp
        f8 = (T._MONO, 8, "bold")
        tw = _text_w(f8, text) + 12
        chip_h = 16
        cyb = y1 - chip_h - 4
        cyb = max(2, cyb)
        c.create_rectangle(x1, cyb, x1 + tw, cyb + chip_h,
                           fill="#07101c", outline=col, width=1)
        c.create_text(x1 + tw / 2, cyb + chip_h / 2, text=text,
                      fill=col, font=f8)

        # person: glowing head marker so HUMANS pop instantly
        if t.cls == 0:
            a = 0.4 + 0.4 * (0.5 + 0.5 * __import__("math").sin(now * 6.0))
            c.create_oval(x1 - 3, cyb - 6, x2 + 3, cyb - 2,
                          outline=T.mix("#4dffa0", T.VPORT_IN, 1.0 - a),
                          width=2)
        # moving things: little speed streak under the box
        if getattr(t, "moving", False):
            px = max(3, int(8 * min(1.0, abs(t.est_kmh) / 60.0)))
            c.create_line(x2 + 2, y2, x2 + 2 + px, y2, fill=col, width=2)

    def _hud(self, c, W, H, hz, st, now):
        if st is not None and self._p("show_hud") and st.speed_limit:
            cx, cy, r = W // 2, 62, 24
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=T.ACC, width=3, fill="#0a1626")
            c.create_text(cx, cy - 2, text=str(st.speed_limit), fill=T.FG,
                          font=(T._MONO, 17, "bold"))
            c.create_text(cx, cy + 12, text="LIMIT", fill=T.FG_FAINT,
                          font=(T._MONO, 7, "bold"))

        if st is not None and self._p("show_hud") and (self.armed or (st.thinking and st.plan)):
            ribbon = ", ".join(st.thinking[:2]) if st.thinking else "scanning"
            dots = "." * (1 + int(now * 2.5) % 3) if self.armed else ""
            row = ("ARMED\u00b7" + ribbon + dots) if self.armed else ribbon
            c.create_rectangle(10, hz + 8, 16 + len(row) * 7 + 10, hz + 26,
                               fill="#0a1626", outline=T.ACC, width=1)
            c.create_text(24, hz + 24, text=row, fill="#64e6ff",
                          font=(T._FAM, 10, "bold"), anchor="w")

        if st is not None and self._p("show_hud") and st.thinking:
            y = H - 34
            for line in reversed(st.thinking[-4:]):
                c.create_text(14, y, text=line, fill=T.FG_DIM,
                              font=(T._FAM, 9), anchor="w")
                y -= 15

    @staticmethod
    def _fade(hexcol: str) -> str:
        r = int(hexcol[1:3], 16)
        g = int(hexcol[3:5], 16)
        b = int(hexcol[5:7], 16)
        bg = (4, 6, 11)
        return f"#{int(r * 0.28 + bg[0] * 0.72):02x}" \
               f"{int(g * 0.28 + bg[1] * 0.72):02x}" \
               f"{int(b * 0.28 + bg[2] * 0.72):02x}"


def _text_w(font, s, caps=7.2):
    """Rough pixel width of a monospace string on the viewport canvas."""
    return int(len(s) * caps)