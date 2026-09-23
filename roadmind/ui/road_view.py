"""Tesla-style live vision view using Tk Canvas: dimmed game frame + 3D overlay."""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

BG = "#0a0e14"


def _bgra_to_rgb_bytes(frame):
    rgb = frame[:, :, :3][:, :, ::-1]
    return rgb.tobytes()


class RoadView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.frame = None
        self.state = None
        self.armed = False
        self._photo = None

    def set_frame(self, frame, state):
        self.frame = frame
        self.state = state

    # -- drawing --------------------------------------------------------
    def _draw(self):
        c = self.canvas
        c.delete("all")
        W_px = c.winfo_width()
        H_px = c.winfo_height()
        if W_px < 10 or H_px < 10:
            return
        c.create_rectangle(0, 0, W_px, H_px, fill=BG, outline="")

        if self.frame is not None:
            h, w = self.frame.shape[:2]
            img = Image.frombytes("RGB", (w, h), _bgra_to_rgb_bytes(self.frame))
            scale = max(W_px / w, H_px / h)
            nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
            img = img.resize((nw, nh), Image.BILINEAR)
            x0 = (nw - W_px) // 2
            y0 = (nh - H_px) // 2
            img = img.crop((x0, y0, x0 + W_px, y0 + H_px))
            img = img.point(lambda v: int(v * 0.62))  # dim for overlay legibility
            self._photo = ImageTk.PhotoImage(img)
            c.create_image(0, 0, image=self._photo, anchor="nw")

        st = self.state
        hz = int(H_px * 0.42)
        vp_x = W_px / 2

        if st is not None and st.lanes.get("valid"):
            off = st.lanes.get("offset", 0.0)
            ang = st.lanes.get("angle", 0.0)
            vpx = vp_x + off * W_px * -0.5 + ang * W_px * 0.15
            c.create_line(int(W_px * 0.16), H_px, int(vpx - W_px * 0.06), hz,
                          fill="#50dcff", width=2)
            c.create_line(int(W_px * 0.84), H_px, int(vpx + W_px * 0.06), hz,
                          fill="#50dcff", width=2)
            c.create_line(int(W_px * 0.48), H_px, int(vpx), hz,
                          fill="#50dcff", width=3, dash=(10, 8))

        if st is not None and st.tracks:
            for t in st.tracks:
                cx = vp_x + (t.x - 0.5) * W_px * 1.6
                cy = H_px * (0.62 + (t.y - 0.6) * 0.9)
                bw = int(t.w * W_px * 3.2)
                bh = int(t.h * H_px * 1.6)
                self._vehicle(c, cx, cy, bw, bh, t.label, t.h)

        self._hud(c, W_px, H_px, hz, st)
        c.tag_lower("bg")

    def _vehicle(self, c, cx, cy, bw, bh, label, hf):
        if bh < 4 or bw < 3:
            return
        if hf > 0.15:
            col = "#ff5a46"
        elif hf > 0.08:
            col = "#ffaa3c"
        else:
            col = "#ffcc3c"
        depth = max(3, min(22, int(bh * 0.55)))
        x1, y1 = int(cx - bw / 2), int(cy - bh / 2)
        x2, y2 = int(cx + bw / 2), int(cy + bh / 2)
        c.create_rectangle(x1, y1, x2, y2, outline=col, width=2,
                           fill=_hex_fade(col))
        dx = x1 + depth
        dy = y1 - depth // 2
        c.create_rectangle(dx, dy, dx + bw, dy + bh, outline=col, width=2,
                           fill=_hex_fade(col))
        c.create_line(x1, y1, dx, dy, fill=col, width=2)
        c.create_line(x2, y1, dx + bw, dy, fill=col, width=2)
        c.create_line(x1, y2, dx, dy + bh, fill=col, width=2)
        c.create_line(x2, y2, dx + bw, dy + bh, fill=col, width=2)
        if label == "person":
            c.create_oval(cx - 5, y1 - 14, cx + 5, y1 - 4, outline="#50ff8c",
                          width=2, fill="#50ff8c")

    def _hud(self, c, W, H, hz, st):
        # speed limit dial
        if st is not None and st.speed_limit:
            cx, cy, r = W // 2, 26, 22
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#ffffff",
                          width=2)
            c.create_text(cx, cy, text=str(st.speed_limit), fill="#ffffff",
                          font=("Helvetica", 16, "bold"))
            c.create_text(cx, cy + r + 8, text="LIMIT", fill="#c8c8c8",
                          font=("Helvetica", 8))
        # intent ribbon
        if st is not None and (self.armed or (st.thinking and st.plan)):
            text = ", ".join(st.thinking[:2]) if st.thinking else "scanning"
            c.create_text(14, hz + 16, text=("ARMED · " if self.armed else "") + text,
                          fill="#64e6ff", font=("Helvetica", 10, "bold"),
                          anchor="w")
        # thinking log
        if st is not None and st.thinking:
            y = H - 16
            for line in reversed(st.thinking[-4:]):
                c.create_text(14, y, text=line, fill="#b4c8dc",
                              font=("Helvetica", 8), anchor="w")
                y -= 13
        c.create_text(W - 8, H - 14, text="ROADMIND", fill="#788ca0",
                      font=("Helvetica", 8), anchor="e")


def _hex_fade(hexcol: str) -> str:
    """24%-alpha look: blend toward the background for fills."""
    r = int(hexcol[1:3], 16)
    g = int(hexcol[3:5], 16)
    b = int(hexcol[5:7], 16)
    bg = (10, 14, 20)
    r2 = int(r * 0.28 + bg[0] * 0.72)
    g2 = int(g * 0.28 + bg[1] * 0.72)
    b2 = int(b * 0.28 + bg[2] * 0.72)
    return f"#{r2:02x}{g2:02x}{b2:02x}"