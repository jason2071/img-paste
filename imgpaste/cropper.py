"""Crop & annotate editor — ลากรูปเข้า -> crop -> วาด (rect/oval/line) + สี
-> Save / Paste. รันเป็น process แยก: python -m imgpaste.cropper [path]

Paste = copy รูป (crop+วาด) เข้า clipboard + auto Cmd/Ctrl+V เข้า app ก่อนหน้า.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import colorchooser, filedialog

from PIL import Image, ImageDraw, ImageTk

from . import config as cfg_mod
from . import paste
from .clipboard import copy_image

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except Exception:
    _HAS_DND = False

_MAX_W, _MAX_H = 1000, 680      # ขนาดแสดงผลสูงสุด (scale-to-fit)
_BG = "#15181e"
_PANEL = "#1e232b"
_SWATCHES = ["#ff3b30", "#34c759", "#0a84ff", "#ffd60a", "#ffffff", "#000000"]
_TOOLS = [("▭", "rect"), ("◯", "oval"), ("╱", "line")]


class _Tooltip:
    """tooltip ง่าย ๆ โผล่ตอน hover ปุ่ม."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#2b3340", fg="#e6e9ee",
                 font=("Helvetica", 10), padx=8, pady=4).pack()

    def _hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def _capture_region() -> str | None:
    """ลากเลือกพื้นที่จอ (เหมือน Cmd+Shift+4) -> คืน path ภาพ หรือ None ถ้ายกเลิก."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        subprocess.run(["screencapture", "-i", "-x", tmp.name], check=False)
    except Exception:
        return None
    if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
        return tmp.name
    return None


class Cropper:
    def __init__(self, path: str | None = None, capture: bool = False):
        self.cfg = cfg_mod.load()
        if capture:
            captured = _capture_region()
            if captured:
                path = captured
        self.orig: Image.Image | None = None   # PIL ปัจจุบัน (full-res, หลัง crop)
        self.scale = 1.0
        self.tkimg = None
        self.mode = "crop"                      # crop | annotate
        self.tool = "rect"
        self.color = "#ff3b30"
        self.width = 4
        self.shapes: list[dict] = []            # display coords
        self._start = None
        self._tmp = None
        self._band = None

        self.root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
        self.root.title("ImgPaste — Crop & Annotate")
        self.root.configure(bg=_BG)

        self._build_toolbar()
        self._status = tk.Label(self.root, text="", bg=_BG, fg="#6b7686",
                                font=("Helvetica", 11), anchor="w", padx=12)
        self._status.pack(fill="x")
        self.canvas = tk.Canvas(self.root, bg=_BG, highlightthickness=0,
                                width=_MAX_W, height=_MAX_H)
        self.canvas.pack(anchor="nw", padx=10, pady=(0, 10))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # keyboard shortcuts
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Command-z>", lambda e: self._undo())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Command-s>", lambda e: self._save())
        self.root.bind("<Command-Return>", lambda e: self._paste())
        self.root.bind("r", lambda e: self._set_tool("rect"))
        self.root.bind("o", lambda e: self._set_tool("oval"))
        self.root.bind("l", lambda e: self._set_tool("line"))

        if _HAS_DND:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<Drop>>", self._on_drop)

        if path and os.path.isfile(path):
            self._load(path)
        else:
            self._show_dropzone()
        self._update_toolbar()

        # ขึ้นหน้าให้เห็น (โดยเฉพาะหลัง capture)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def _on_escape(self, _e=None):
        # crop mode -> ยกเลิก crop (ไม่ปิดหน้าต่าง); ไม่งั้น -> ปิด
        if self.mode == "crop":
            self._to_annotate()
        else:
            self.root.destroy()

    # ---------- toolbar ----------
    def _tbtn(self, parent, text, cmd, **kw):
        opts = dict(relief="flat", bg=_PANEL, fg="#e6e9ee", bd=0, padx=8, pady=4)
        opts.update(kw)
        return tk.Button(parent, text=text, command=cmd, **opts)

    def _sep(self, parent):
        tk.Frame(parent, width=1, height=20, bg="#3a4658").pack(
            side="left", padx=8, pady=2)

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=_BG)
        bar.pack(fill="x", padx=10, pady=10)

        # --- export group ชิดขวา (pack right ก่อน เพื่อกันพื้นที่) ---
        b_send = self._tbtn(bar, "📤 Send", self._paste, padx=12,
                            bg="#0a84ff", fg="white",
                            font=("Helvetica", 12, "bold"))
        b_send.pack(side="right", padx=(3, 0))
        _Tooltip(b_send, "copy รูป + วาง (Cmd+V) เข้า app ที่ focus ก่อนหน้า")
        self._tbtn(bar, "💾 Save", self._save).pack(side="right", padx=3)

        # --- file ---
        self._b_open = self._tbtn(bar, "Open…", self._open_dialog)
        self._b_open.pack(side="left", padx=(0, 0))
        self._sep(bar)
        # --- crop ---
        self._b_crop = self._tbtn(bar, "✂ Crop", self._do_crop)
        self._b_crop.pack(side="left", padx=3)
        self._b_annot = self._tbtn(bar, "✕ Cancel", self._to_annotate)
        self._b_annot.pack(side="left", padx=3)
        self._sep(bar)
        # --- tools ---
        self._tool_btns = {}
        for label, name in _TOOLS:
            b = self._tbtn(bar, label, lambda n=name: self._set_tool(n),
                           width=2, padx=6)
            b.pack(side="left", padx=2)
            self._tool_btns[name] = b
        self._sep(bar)
        # --- color + stroke --- (ใช้ Frame: macOS tk.Button ไม่ honor bg)
        for c in _SWATCHES:
            sw = tk.Frame(bar, bg=c, width=20, height=20, highlightthickness=1,
                          highlightbackground="#3a4658", cursor="hand2")
            sw.pack(side="left", padx=2)
            sw.bind("<Button-1>", lambda e, col=c: self._set_color(col))
        self._tbtn(bar, "🎨", self._pick_color, padx=6).pack(side="left", padx=(6, 4))
        self._sw_cur = tk.Label(bar, bg=self.color, width=3)
        self._sw_cur.pack(side="left", padx=4)
        self._stroke = tk.IntVar(value=self.width)
        tk.Spinbox(bar, from_=1, to=14, width=3, textvariable=self._stroke,
                   bg=_PANEL, fg="#e6e9ee", bd=0, highlightthickness=0,
                   buttonbackground=_PANEL,
                   command=self._set_width).pack(side="left", padx=(0, 0))
        self._sep(bar)
        # --- history ---
        self._tbtn(bar, "↶ Undo", self._undo).pack(side="left", padx=3)

    def _set_width(self):
        try:
            self.width = max(1, int(self._stroke.get()))
        except (tk.TclError, ValueError):
            pass
        self._update_toolbar()

    def _update_toolbar(self):
        has = self.orig is not None
        crop = self.mode == "crop"
        self._b_crop.configure(state="normal" if has else "disabled",
                               text="✓ Apply crop" if crop else "✂ Crop")
        self._b_annot.configure(state="normal" if crop else "disabled")
        for name, b in self._tool_btns.items():
            sel = (self.mode == "annotate" and self.tool == name)
            b.configure(bg="#3a4658" if sel else _PANEL)
        self._status.configure(text=self._status_text())

    def _status_text(self) -> str:
        if self.orig is None:
            return "ลากรูปมาวางที่นี่ หรือกด Open…" if _HAS_DND else "กด Open… เลือกรูป"
        if self.mode == "crop":
            return "ลากกรอบเลือกพื้นที่ → ✓ Apply crop   ·   Esc = ยกเลิก crop"
        names = {"rect": "Rectangle", "oval": "Oval", "line": "Line"}
        return (f"Tool: {names.get(self.tool, self.tool)}   ·   เส้น {self.width}px"
                f"   ·   ลากบนรูปเพื่อวาด   ·   {len(self.shapes)} annotations"
                f"   ·   Cmd+Z undo · Cmd+↵ Send · Esc close")

    # ---------- image load / display ----------
    def _show_dropzone(self):
        self.canvas.delete("all")
        msg = "ลากรูปมาวางที่นี่" if _HAS_DND else "กด Open… เพื่อเลือกรูป"
        self.canvas.create_text(_MAX_W / 2, _MAX_H / 2, text=msg,
                                 fill="#6b7686", font=("Helvetica", 20))

    def _open_dialog(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp *.heic")])
        if p:
            self._load(p)
            self._update_toolbar()

    def _on_drop(self, event):
        try:
            p = self.root.tk.splitlist(event.data)[0]
        except Exception:
            p = event.data
        if p and os.path.isfile(p):
            self._load(p)
            self._update_toolbar()

    def _load(self, path: str):
        try:
            self.orig = Image.open(path).convert("RGBA")
        except Exception:
            return
        self.shapes.clear()
        self.mode = "annotate"    # drop/open เสร็จ -> โชว์ preview วาดได้เลย
        self._display()

    def _display(self):
        w, h = self.orig.size
        self.scale = min(_MAX_W / w, _MAX_H / h, 1.0)
        dw, dh = max(1, int(w * self.scale)), max(1, int(h * self.scale))
        disp = self.orig.resize((dw, dh))
        self.tkimg = ImageTk.PhotoImage(disp)
        self.canvas.configure(width=dw, height=dh)
        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        if self.tkimg is not None:
            self.canvas.create_image(0, 0, image=self.tkimg, anchor="nw")
        for s in self.shapes:
            self._draw_shape(s)

    def _draw_shape(self, s):
        x0, y0, x1, y1 = s["x0"], s["y0"], s["x1"], s["y1"]
        if s["tool"] == "rect":
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=s["color"],
                                         width=s["width"])
        elif s["tool"] == "oval":
            self.canvas.create_oval(x0, y0, x1, y1, outline=s["color"],
                                    width=s["width"])
        else:
            self.canvas.create_line(x0, y0, x1, y1, fill=s["color"],
                                    width=s["width"])

    # ---------- tools / color ----------
    def _set_tool(self, name):
        self.tool = name
        if self.mode != "annotate":
            self._to_annotate()
        self._update_toolbar()

    def _set_color(self, c):
        self.color = c
        self._sw_cur.configure(bg=c)

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color)[1]
        if c:
            self._set_color(c)

    def _to_annotate(self):
        if self.orig is None:
            return
        self.mode = "annotate"
        if self._band is not None:
            self.canvas.delete(self._band)
            self._band = None
        self._update_toolbar()

    def _undo(self):
        if self.shapes:
            self.shapes.pop()
            self._redraw()
            self._update_toolbar()

    # ---------- mouse ----------
    def _on_press(self, e):
        if self.orig is None:
            return
        self._start = (e.x, e.y)
        if self.mode == "crop":
            if self._band is not None:
                self.canvas.delete(self._band)
            self._band = self.canvas.create_rectangle(
                e.x, e.y, e.x, e.y, outline="#0a84ff", width=2, dash=(5, 4))
        else:
            self._tmp = None

    def _on_drag(self, e):
        if self._start is None:
            return
        x0, y0 = self._start
        if self.mode == "crop":
            self.canvas.coords(self._band, x0, y0, e.x, e.y)
        else:
            if self._tmp is not None:
                self.canvas.delete(self._tmp)
            if self.tool == "rect":
                self._tmp = self.canvas.create_rectangle(
                    x0, y0, e.x, e.y, outline=self.color, width=self.width)
            elif self.tool == "oval":
                self._tmp = self.canvas.create_oval(
                    x0, y0, e.x, e.y, outline=self.color, width=self.width)
            else:
                self._tmp = self.canvas.create_line(
                    x0, y0, e.x, e.y, fill=self.color, width=self.width)

    def _on_release(self, e):
        if self._start is None:
            return
        x0, y0 = self._start
        self._start = None
        if self.mode == "annotate" and (abs(e.x - x0) > 2 or abs(e.y - y0) > 2):
            self.shapes.append({"tool": self.tool, "x0": x0, "y0": y0,
                                "x1": e.x, "y1": e.y, "color": self.color,
                                "width": self.width})
            self._tmp = None
            self._update_toolbar()

    # ---------- crop ----------
    def _do_crop(self):
        if self.orig is None:
            return
        # คลิกครั้งแรก: เข้า crop mode (ลากเลือกกรอบ)
        if self.mode != "crop":
            self.mode = "crop"
            if self._band is not None:
                self.canvas.delete(self._band)
                self._band = None
            self._update_toolbar()
            return
        # อยู่ใน crop mode + คลิก Apply: ครอปตามกรอบ
        if self._band is not None:
            x0, y0, x1, y1 = self.canvas.coords(self._band)
            if abs(x1 - x0) >= 5 and abs(y1 - y0) >= 5:
                inv = 1.0 / self.scale
                box = (int(min(x0, x1) * inv), int(min(y0, y1) * inv),
                       int(max(x0, x1) * inv), int(max(y0, y1) * inv))
                self.orig = self.orig.crop(box)
                self.shapes.clear()
            self.canvas.delete(self._band)
            self._band = None
        self.mode = "annotate"
        self._display()
        self._update_toolbar()

    # ---------- export ----------
    def _flatten(self) -> Image.Image:
        img = self.orig.copy()
        d = ImageDraw.Draw(img)
        inv = 1.0 / self.scale
        for s in self.shapes:
            x0, y0 = s["x0"] * inv, s["y0"] * inv
            x1, y1 = s["x1"] * inv, s["y1"] * inv
            w = max(1, int(round(s["width"] * inv)))
            col = s["color"]
            if s["tool"] == "line":
                d.line([x0, y0, x1, y1], fill=col, width=w)
            else:
                box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
                if s["tool"] == "rect":
                    d.rectangle(box, outline=col, width=w)
                else:
                    d.ellipse(box, outline=col, width=w)
        return img

    def _save(self):
        if self.orig is None:
            return
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG", "*.png")])
        if p:
            self._flatten().convert("RGB").save(p)

    def _paste(self):
        if self.orig is None:
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        self._flatten().save(tmp.name)
        copy_image(tmp.name)
        self.root.destroy()
        time.sleep(self.cfg.paste_delay)
        if paste.available():
            paste.paste()

    def run(self):
        self.root.mainloop()


def run(path: str | None = None, capture: bool = False):
    Cropper(path, capture).run()


if __name__ == "__main__":
    args = sys.argv[1:]
    cap = "--capture" in args
    files = [a for a in args if not a.startswith("-")]
    run(files[0] if files else None, cap)
