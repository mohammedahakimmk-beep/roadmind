"""Tesla-style live vision view using Tk Canvas: dimmed game frame + 3D overlay.

The whole viewport is a rounded dark "bezel box" (see the RoundedPanel that
hosts it): a crisp inner border, a live badge, the game name and FPS - so it
reads as a proper screen inside the app, like a real product.
"""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from . import theme as T


def _bgra_to_rgb_bytes(frame):
    return frame[:, :, :3][:, :, ::-1].tobytes()


class RoadView(tk.Frame):
    def __init__(self, master, game_label="pick a game window"):
        super().__init__(master, bg=T.VPORT_IN, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=T.VPORT_IN, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.frame = None
        self.state = None
        self.armed = False
        self.game_label = game_label
        self._photo = None

    def set_frame(self, frame, state):
        self.frame = frame
        self.state = state

    # -- drawing --------------------------------------------------------
    def _draw(self):
        c = self.canvas
        c.delete("all")
        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return

        if self.frame is not None:
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

        st = self.state
        hz = int(H * 0.42)
        vpx = W / 2

        if st is not None and st.lanes.get("valid"):
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

        if st is not None and st.tracks:
            for t in st.tracks:
                cx = vpx + (t.x - 0.5) * W * 1.6
                cy = H * (0.62 + (t.y - 0.6) * 0.9)
                bw = int(t.w * W * 3.2)
                bh = int(t.h * H * 1.6)
                self._vehicle(c, cx, cy, bw, bh, t.label, t.h)

        self._chrome(c, W, H)
        self._hud(c, W, H, hz, st)

    def _chrome(self, c, W, H):
        """The 'screen' frame: crisp border + status bar like a real device."""
        c.create_rectangle(1, 1, W - 2, H - 2, outline=T.VPORT_BEZEL, width=1)
        live = self.frame is not None
        # top status strip
        c.create_rectangle(0, 0, W, 30, fill="#06090f", outline="")
        c.create_line(0, 30, W, 30, fill=T.VPORT_BEZEL, width=1)
        dot = T.GREEN if live else T.FG_FAINT
        c.create_oval(12, 20, 20, 28, fill=dot, outline=dot)
        c.create_text(26, 24, text="LIVE VISION" if live else "VISION STANDBY",
                      fill=(T.GREEN if live else T.FG_FAINT),
                      font=(T._FAM, 9, "bold"), anchor="w")
        c.create_text(W - 12, 24, text=self.game_label,
                      fill=T.FG_DIM, font=(T._FAM, 9), anchor="e")
        # bottom strip
        c.create_line(0, H - 22, W, H - 22, fill=T.VPORT_BEZEL, width=1)
        c.create_text(W - 12, H - 12, text="ROADMIND \u00b7 open-source autopilot",
                      fill=T.FG_FAINT, font=(T._FAM, 8), anchor="e")

    def _vehicle(self, c, cx, cy, bw, bh, label, hf):
        if bh < 4 or bw < 3:
            return
        col = "#ff4d5e" if hf > 0.15 else ("#ff9f2e" if hf > 0.08 else "#ffce3a")
        depth = max(3, min(22, int(bh * 0.55)))
        x1, y1 = int(cx - bw / 2), int(cy - bh / 2)
        x2, y2 = int(cx + bw / 2), int(cy + bh / 2)
        c.create_rectangle(x1, y1, x2, y2, outline=col, width=2, fill=self._fade(col))
        dx = x1 + depth
        dy = y1 - depth // 2
        c.create_rectangle(dx, dy, dx + bw, dy + bh, outline=col, width=2,
                           fill=self._fade(col))
        c.create_line(x1, y1, dx, dy, fill=col, width=2)
        c.create_line(x2, y1, dx + bw, dy, fill=col, width=2)
        c.create_line(x1, y2, dx, dy + bh, fill=col, width=2)
        c.create_line(x2, y2, dx + bw, dy + bh, fill=col, width=2)
        if label == "person":
            c.create_oval(cx - 5, y1 - 14, cx + 5, y1 - 4, outline="#4dffa0",
                          width=2, fill="#4dffa0")
        c.create_text(x1, y1 - 8, text=label.upper(), fill=col,
                      font=(T._MONO, 7, "bold"), anchor="w")

    def _hud(self, c, W, H, hz, st):
        if st is not None and st.speed_limit:
            cx, cy, r = W // 2, 62, 24
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=T.ACC, width=3, fill="#0a1626")
            c.create_text(cx, cy - 2, text=str(st.speed_limit), fill=T.FG,
                          font=(T._MONO, 17, "bold"))
            c.create_text(cx, cy + 12, text="LIMIT", fill=T.FG_FAINT,
                          font=(T._MONO, 7, "bold"))

        if st is not None and (self.armed or (st.thinking and st.plan)):
            ribbon = ", ".join(st.thinking[:2]) if st.thinking else "scanning"
            row = ("ARMED \u00b7 " + ribbon) if self.armed else ribbon
            c.create_rectangle(10, hz + 8, 16 + len(row) * 7 + 10, hz + 26,
                               fill="#0a1626", outline=T.ACC, width=1)
            c.create_text(24, hz + 24, text=row, fill="#64e6ff",
                          font=(T._FAM, 10, "bold"), anchor="w")

        if st is not None and st.thinking:
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