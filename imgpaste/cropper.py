"""Crop & annotate editor — capture/drag รูป -> preview -> วาด -> Save / Send.

UI สไตล์ CleanShot: floating icon toolbar กลางใต้ภาพ + flyout เลือก shape/stroke/สี.
รันเป็น process แยก: python -m imgpaste.cropper [path] [--capture]
Send = copy (crop+วาด) เข้า clipboard + auto Cmd/Ctrl+V เข้า app ก่อนหน้า.
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

try:
    from AppKit import NSWorkspace

    def _frontmost():
        try:
            return NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            return None
except Exception:
    def _frontmost():
        return None

# ---- theme ----
_BG = "#14161b"             # window padding (Tk โปร่งใสบน macOS ไม่ได้ -> dark card)
_TB_BG = "#ffffff"          # toolbar/flyout pill
_TB_BORDER = "#d8d8de"
_ICON = "#3c3c43"
_ICON_HOT = "#000000"
_ICON_OFF = "#b0b0b8"
_ACTIVE_BG = "#dbe7ff"          # ฟ้าอ่อน — active เด่นชัด
_ACTIVE_FG = "#0a6cff"          # icon สีฟ้า accent ตอน active
_ACTIVE_RING = "#9bc0ff"
_DONE_BG = "#34c759"
_CANCEL = "#ff3b30"
_SEP = "#e3e3e8"
_SWATCHES = ["#ff3b30", "#ff9f0a", "#34c759", "#0a84ff", "#bf5af2",
             "#ffffff", "#000000"]
_STROKES = [("S", 2), ("M", 5), ("L", 9)]
_HOVER_BG = "#f1f2f7"
_MAX_W, _MAX_H = 1100, 720
_IFONT = ("Helvetica", 16)
_IFONT_SM = ("Helvetica", 14)
_TB_H = 48
_PILL_R = 16
_BW, _SEPW, _PAD = 36, 15, 13


def _rr(cv, x1, y1, x2, y2, r, **kw):
    """rounded rectangle polygon."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def _draw_icon(cv, name, x, y, col, w=2.0):
    """วาด line icon แบบ vector (stroke เท่ากัน round caps)."""
    def L(*p, **k):
        cv.create_line(*p, fill=col, width=w, capstyle="round",
                       joinstyle="round", **k)

    if name == "rect":
        _rr(cv, x - 7, y - 6, x + 7, y + 6, 3, outline=col, width=w, fill="")
    elif name == "oval":
        cv.create_oval(x - 7, y - 7, x + 7, y + 7, outline=col, width=w)
    elif name == "line":
        L(x - 7, y + 6, x + 7, y - 6)
    elif name == "close":
        L(x - 6, y - 6, x + 6, y + 6)
        L(x - 6, y + 6, x + 6, y - 6)
    elif name == "check":
        L(x - 6, y + 1, x - 2, y + 5, x + 7, y - 6)
    elif name == "copy":
        _rr(cv, x - 7, y - 7, x + 2, y + 2, 2, outline=col, width=w, fill="")
        _rr(cv, x - 2, y - 2, x + 7, y + 7, 2, outline=col, width=w, fill=_TB_BG)
    elif name == "save":
        L(x, y - 7, x, y + 3)
        L(x - 4, y - 1, x, y + 3, x + 4, y - 1)
        L(x - 6, y + 7, x + 6, y + 7)
    elif name == "crop":
        L(x - 8, y - 3, x + 5, y - 3, x + 5, y + 8)
        L(x - 5, y - 8, x - 5, y + 3, x + 8, y + 3)
    elif name == "undo":
        cv.create_arc(x - 7, y - 6, x + 6, y + 8, start=20, extent=250,
                      style="arc", outline=col, width=w)
        L(x - 7, y - 3, x - 6, y - 7, x - 2, y - 6)
    elif name == "redo":
        cv.create_arc(x - 6, y - 6, x + 7, y + 8, start=-90, extent=250,
                      style="arc", outline=col, width=w)
        L(x + 7, y - 3, x + 6, y - 7, x + 2, y - 6)


class _Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _e=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#2b2b30", fg="#f2f2f5",
                 font=("Helvetica", 10), padx=7, pady=3).pack()

    def _hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def _capture_region() -> str | None:
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
            c = _capture_region()
            if c:
                path = c
        self.orig: Image.Image | None = None
        self.scale = 1.0
        self.tkimg = None
        self.mode = "annotate"          # crop | annotate
        self.tool = None                # ยังไม่เลือก tool ตอนเปิด
        self.color = "#ff3b30"
        self.width = 5
        self.shapes: list[dict] = []
        self._redo: list[dict] = []
        self._start = None
        self._tmp = None
        self._band = None
        self._fly_open = False           # submenu (stroke/สี) โผล่ตอนคลิก shape tool
        # จำ app ที่ active อยู่ก่อนหน้า (เป้าหมายของ Send/paste)
        self._prev_app = _frontmost()

        self.root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
        self.root.title("ImgPaste")
        self.root.configure(bg=_BG)
        self.root.resizable(False, False)
        self.root.withdraw()                 # ซ่อนจนกว่าจะจัดกลาง (กันวาบมุมซ้ายบน)
        # ลากพื้นที่ขอบเพื่อย้ายหน้าต่าง
        self.root.bind("<ButtonPress-1>", self._move_start, add="+")
        self.root.bind("<B1-Motion>", self._move_drag, add="+")

        self.canvas = tk.Canvas(self.root, bg=_BG, highlightthickness=0,
                                width=640, height=420)
        self.canvas.pack(padx=22, pady=(22, 0))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._build_toolbar()
        self._build_flyout()
        self._botpad = tk.Frame(self.root, height=18, bg=_BG)
        self._botpad.pack()

        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Command-z>", lambda e: self._undo())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Command-Shift-Z>", lambda e: self._do_redo())
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
        self._refresh()

        # borderless ลอย (เหมือน wheel): ตั้ง override + จัดกลาง "ขณะยังซ่อน"
        # แล้ว deiconify ครั้งเดียว -> โผล่กลางจอ borderless เลย ไม่วาบ
        self.root.overrideredirect(True)
        self._center()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()

        # borderless Tk ไม่รับ keyDown -> global Esc listener ปิดหน้าต่าง
        self._esc_listener = None
        try:
            from pynput import keyboard as _pk

            def _gk(key):
                if key == _pk.Key.esc:
                    self.root.after(0, self._on_escape)
            self._esc_listener = _pk.Listener(on_press=_gk)
            self._esc_listener.start()
        except Exception:
            pass

    def _quit(self):
        if self._esc_listener is not None:
            try:
                self._esc_listener.stop()
            except Exception:
                pass
            self._esc_listener = None
        self.root.destroy()

    def _center(self):
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")

    def _move_start(self, e):
        self._mx, self._my = e.x, e.y

    def _move_drag(self, e):
        x = self.root.winfo_x() + e.x - getattr(self, "_mx", e.x)
        y = self.root.winfo_y() + e.y - getattr(self, "_my", e.y)
        self.root.geometry(f"+{x}+{y}")

    # ---------- toolbar: 2 pills (tools | actions) ----------
    _TOOLS = [("undo", "undo"), ("redo", "redo"), ("sep",),
              ("crop", "crop"), ("sep",),
              ("rect", "rect"), ("oval", "oval"), ("line", "line")]
    _ACTIONS = [("close", "close"), ("copy", "copy"), ("save", "save"),
                ("done", "check")]

    def _build_toolbar(self):
        self._hover = None
        row = tk.Frame(self.root, bg=_BG)
        row.pack(pady=(16, 0))
        self._tools_cv, self._tools_lay = self._mk_pill(row, self._TOOLS)
        self._tools_cv.pack(side="left")
        tk.Frame(row, width=16, bg=_BG).pack(side="left")
        self._act_cv, self._act_lay = self._mk_pill(row, self._ACTIONS)
        self._act_cv.pack(side="left")

    def _mk_pill(self, parent, specs):
        layout, x = [], _PAD
        for s in specs:
            if s[0] == "sep":
                layout.append(("sep", x + _SEPW / 2))
                x += _SEPW
            else:
                layout.append((s[0], s[1], x, x + _BW))
                x += _BW
        cv = tk.Canvas(parent, width=x + _PAD, height=_TB_H, bg=_BG,
                       highlightthickness=0, cursor="hand2")
        cv.bind("<Button-1>", lambda e, L=layout: self._pill_click(e, L))
        cv.bind("<Motion>", lambda e, L=layout: self._set_hover(self._at(e.x, L)))
        cv.bind("<Leave>", lambda e: self._set_hover(None))
        return cv, layout

    def _at(self, px, layout):
        for it in layout:
            if it[0] != "sep" and it[2] <= px <= it[3]:
                return it[0]
        return None

    def _set_hover(self, bid):
        if bid != self._hover:
            self._hover = bid
            self._draw_pills()

    def _pill_click(self, e, layout):
        bid = self._at(e.x, layout)
        actions = {
            "undo": self._undo, "redo": self._do_redo, "crop": self._do_crop,
            "rect": lambda: self._set_tool("rect"),
            "oval": lambda: self._set_tool("oval"),
            "line": lambda: self._set_tool("line"),
            "close": self._on_escape, "copy": self._copy_only,
            "save": self._save, "done": self._paste,
        }
        if bid in actions:
            actions[bid]()

    def _draw_pills(self):
        self._draw_pill(self._tools_cv, self._tools_lay)
        self._draw_pill(self._act_cv, self._act_lay)

    def _draw_pill(self, cv, layout):
        cv.delete("all")
        W, H = int(cv["width"]), _TB_H
        cy = (4 + H - 6) / 2
        _rr(cv, 4, 8, W - 4, H - 2, _PILL_R, fill="#d9dae2", outline="")
        _rr(cv, 4, 4, W - 4, H - 8, _PILL_R, fill=_TB_BG, outline="#e7e8ee")
        has = self.orig is not None
        crop = self.mode == "crop"
        for it in layout:
            if it[0] == "sep":
                cv.create_line(it[1], cy - 10, it[1], cy + 10, fill=_SEP, width=1)
                continue
            bid, icon, x0, x1 = it
            cx = (x0 + x1) / 2
            active = ((bid == "crop" and crop) or
                      (bid in ("rect", "oval", "line") and has and not crop
                       and self.tool == bid))
            if bid == "done":
                _rr(cv, cx - 16, cy - 14, cx + 16, cy + 14, 10, fill=_DONE_BG,
                    outline="")
                _draw_icon(cv, "check", cx, cy, "#ffffff")
                continue
            if active:
                _rr(cv, cx - 16, cy - 14, cx + 16, cy + 14, 9, fill=_ACTIVE_BG,
                    outline=_ACTIVE_RING, width=1)
            elif self._hover == bid:
                _rr(cv, cx - 16, cy - 14, cx + 16, cy + 14, 9, fill=_HOVER_BG,
                    outline="")
            col = _CANCEL if bid == "close" else (_ACTIVE_FG if active else _ICON)
            _draw_icon(cv, icon, cx, cy, col)

    # ---------- flyout: stroke+color, ยื่นออกใต้ปุ่ม shape ที่คลิก ----------
    def _build_flyout(self):
        reg, x = [], 14
        for _l, px in _STROKES:
            reg.append(("stroke", px, x, x + 30))
            x += 30
        reg.append(("sepf", x + 9))
        x += 18
        for col in _SWATCHES:
            reg.append(("color", col, x, x + 28))
            x += 28
        self._fly_reg = reg
        self._fly_w = x + 14
        self._flyout = tk.Canvas(self.root, width=self._fly_w, height=42,
                                 bg=_BG, highlightthickness=0, cursor="hand2")
        self._flyout.bind("<Button-1>", self._fly_click)

    def _fly_click(self, e):
        for it in self._fly_reg:
            k = it[0]
            if k == "stroke" and it[2] <= e.x <= it[3]:
                self._set_width(it[1]); return
            if k == "color" and it[2] <= e.x <= it[3]:
                self._set_color(it[1]); return

    def _draw_flyout(self):
        cv = self._flyout
        cv.delete("all")
        W, H = self._fly_w, 42
        cy = H / 2
        # ลูกศรเล็กชี้ขึ้นไปหาปุ่ม (ดู "ยื่นออกจากปุ่ม")
        ax = max(20, min(W - 20, getattr(self, "_fly_arrow_x", W / 2)))
        cv.create_polygon(ax - 7, 8, ax + 7, 8, ax, 1, fill=_TB_BG, outline="")
        _rr(cv, 4, 8, W - 4, H - 2, 14, fill="#d9dae2", outline="")
        _rr(cv, 4, 6, W - 4, H - 6, 14, fill=_TB_BG, outline="#e7e8ee")
        cv.create_polygon(ax - 7, 8, ax + 7, 8, ax, 1, fill=_TB_BG, outline="")
        for it in self._fly_reg:
            if it[0] == "sepf":
                cv.create_line(it[1], cy - 9, it[1], cy + 9, fill=_SEP, width=1)
            elif it[0] == "stroke":
                px, cx = it[1], (it[2] + it[3]) / 2
                r = {2: 3, 5: 5, 9: 8}[px]
                if px == self.width:
                    cv.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                                   outline=_ACTIVE_RING, width=2)
                cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=_ICON, outline="")
            elif it[0] == "color":
                col, cx = it[1], (it[2] + it[3]) / 2
                sel = col.lower() == self.color.lower()
                _rr(cv, cx - 10, cy - 10, cx + 10, cy + 10, 5, fill=col,
                    outline=_ICON_HOT if sel else "#d0d0d6", width=2 if sel else 1)

    def _fly_padx(self):
        # จัด flyout ให้กลาง = อยู่ใต้ปุ่ม shape ที่คลิก (+ ตั้ง _fly_arrow_x)
        cx = None
        for it in self._tools_lay:
            if it[0] == getattr(self, "_fly_btn", None):
                cx = (it[2] + it[3]) / 2
                break
        if cx is None:
            self._fly_arrow_x = self._fly_w / 2
            return 0
        try:
            bx = self._tools_cv.winfo_rootx() - self.root.winfo_rootx() + cx
        except Exception:
            bx = cx
        left = max(0, int(bx - self._fly_w / 2))
        self._fly_arrow_x = bx - left          # ตำแหน่งลูกศรใน flyout
        return (left, 0)

    def _show_flyout(self, show):
        cur = bool(self._flyout.winfo_ismapped())
        if show:
            padx = self._fly_padx()
            self._draw_flyout()
            if not cur:
                self._flyout.pack(anchor="w", padx=padx, pady=(7, 0),
                                  before=self._botpad)
                self.root.after(1, self._refit)
            else:
                self._flyout.pack_configure(padx=padx)
        elif cur:
            self._flyout.pack_forget()
            self.root.after(1, self._refit)

    def _refit(self):
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    # ---------- state refresh ----------
    def _refresh(self):
        has = self.orig is not None
        crop = self.mode == "crop"
        self._draw_pills()
        # submenu (shape/stroke/สี) โผล่ตอนกดปุ่ม shapes
        self._show_flyout(has and not crop and self._fly_open)

    # ---------- image ----------
    def _show_dropzone(self):
        self.canvas.delete("all")
        msg = "ลากรูปมาวางที่นี่" if _HAS_DND else "ใช้เมนู Capture region…"
        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        self.canvas.create_text(w / 2, h / 2, text=msg, fill="#5b6270",
                                 font=("Helvetica", 18))

    def _open_dialog(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp *.heic")])
        if p:
            self._load(p)
            self._refresh()

    def _on_drop(self, event):
        try:
            p = self.root.tk.splitlist(event.data)[0]
        except Exception:
            p = event.data
        if p and os.path.isfile(p):
            self._load(p)
            self._refresh()

    def _load(self, path):
        try:
            self.orig = Image.open(path).convert("RGBA")
        except Exception:
            return
        self.shapes.clear()
        self._redo.clear()
        self.mode = "annotate"
        self._display()

    def _display(self):
        w, h = self.orig.size
        self.scale = min(_MAX_W / w, _MAX_H / h, 1.0)
        dw, dh = max(1, int(w * self.scale)), max(1, int(h * self.scale))
        self.tkimg = ImageTk.PhotoImage(self.orig.resize((dw, dh)))
        self.canvas.configure(width=dw, height=dh)
        self._redraw()
        if self.canvas.winfo_ismapped():
            self.root.after(10, self._center)

    def _redraw(self):
        self.canvas.delete("all")
        if self.tkimg is not None:
            self.canvas.create_image(0, 0, image=self.tkimg, anchor="nw")
        for s in self.shapes:
            self._draw_shape(s)
        # กรอบฟ้า selection border (แบบ line2)
        if self.tkimg is not None:
            dw, dh = self.tkimg.width(), self.tkimg.height()
            self.canvas.create_rectangle(1, 1, dw - 1, dh - 1,
                                         outline="#3b82f6", width=2)

    def _draw_shape(self, s):
        x0, y0, x1, y1 = s["x0"], s["y0"], s["x1"], s["y1"]
        if s["tool"] == "rect":
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=s["color"], width=s["width"])
        elif s["tool"] == "oval":
            self.canvas.create_oval(x0, y0, x1, y1, outline=s["color"], width=s["width"])
        else:
            self.canvas.create_line(x0, y0, x1, y1, fill=s["color"], width=s["width"])

    # ---------- tools/color ----------
    def _set_tool(self, name):
        if self.orig is None:
            return
        # คลิก shape -> เปิด submenu ใต้ปุ่มนั้น; คลิกซ้ำปุ่มเดิม -> ปิด
        if self.mode == "annotate" and self.tool == name and self._fly_open:
            self._fly_open = False
        else:
            self.tool = name
            self._fly_btn = name
            self._fly_open = True
        self.mode = "annotate"
        if self._band is not None:
            self.canvas.delete(self._band)
            self._band = None
        self._refresh()

    def _set_color(self, c):
        self.color = c
        self._refresh()

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color)[1]
        if c:
            self._set_color(c)

    def _set_width(self, px):
        self.width = max(1, int(px))
        self._refresh()

    def _to_annotate(self):
        if self.orig is None:
            return
        self.mode = "annotate"
        if self._band is not None:
            self.canvas.delete(self._band)
            self._band = None
        self._refresh()

    def _undo(self):
        if self.shapes:
            self._redo.append(self.shapes.pop())
            self._redraw()

    def _do_redo(self):
        if self._redo:
            self.shapes.append(self._redo.pop())
            self._redraw()

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
        elif self.tool is not None:
            if self._tmp is not None:
                self.canvas.delete(self._tmp)
            if self.tool == "rect":
                self._tmp = self.canvas.create_rectangle(x0, y0, e.x, e.y, outline=self.color, width=self.width)
            elif self.tool == "oval":
                self._tmp = self.canvas.create_oval(x0, y0, e.x, e.y, outline=self.color, width=self.width)
            else:
                self._tmp = self.canvas.create_line(x0, y0, e.x, e.y, fill=self.color, width=self.width)

    def _on_release(self, e):
        if self._start is None:
            return
        x0, y0 = self._start
        self._start = None
        if (self.mode == "annotate" and self.tool is not None
                and (abs(e.x - x0) > 2 or abs(e.y - y0) > 2)):
            self.shapes.append({"tool": self.tool, "x0": x0, "y0": y0,
                                "x1": e.x, "y1": e.y, "color": self.color,
                                "width": self.width})
            self._redo.clear()
            self._tmp = None

    # ---------- crop ----------
    def _do_crop(self):
        if self.orig is None:
            return
        if self.mode != "crop":
            self.mode = "crop"
            self._fly_open = False           # เข้า crop -> ปิด submenu วาด
            if self._band is not None:
                self.canvas.delete(self._band)
                self._band = None
            self._refresh()
            return
        if self._band is not None:
            x0, y0, x1, y1 = self.canvas.coords(self._band)
            if abs(x1 - x0) >= 5 and abs(y1 - y0) >= 5:
                inv = 1.0 / self.scale
                box = (int(min(x0, x1) * inv), int(min(y0, y1) * inv),
                       int(max(x0, x1) * inv), int(max(y0, y1) * inv))
                self.orig = self.orig.crop(box)
                self.shapes.clear()
                self._redo.clear()
            self.canvas.delete(self._band)
            self._band = None
        self.mode = "annotate"
        self._display()
        self._refresh()

    def _on_escape(self, _e=None):
        if self.mode == "crop":
            self._to_annotate()
        else:
            self._quit()

    # ---------- export ----------
    def _flatten(self) -> Image.Image:
        img = self.orig.copy()
        d = ImageDraw.Draw(img)
        inv = 1.0 / self.scale
        for s in self.shapes:
            x0, y0, x1, y1 = (s["x0"] * inv, s["y0"] * inv, s["x1"] * inv, s["y1"] * inv)
            w = max(1, int(round(s["width"] * inv)))
            if s["tool"] == "line":
                d.line([x0, y0, x1, y1], fill=s["color"], width=w)
            else:
                box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
                if s["tool"] == "rect":
                    d.rectangle(box, outline=s["color"], width=w)
                else:
                    d.ellipse(box, outline=s["color"], width=w)
        return img

    def _save(self):
        if self.orig is None:
            return
        ts = time.strftime("%Y%m%d-%H%M%S")
        p = filedialog.asksaveasfilename(
            initialfile=f"imgpaste-{ts}.png", defaultextension=".png",
            filetypes=[("PNG", "*.png")])
        if p:
            self._flatten().convert("RGB").save(p)

    def _copy_only(self):
        if self.orig is None:
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        self._flatten().save(tmp.name)
        copy_image(tmp.name)

    def _paste(self):
        if self.orig is None:
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        self._flatten().save(tmp.name)
        copy_image(tmp.name)
        self._quit()
        time.sleep(self.cfg.paste_delay)
        # ดึง app เดิมขึ้นมา front ก่อน เพื่อให้ Cmd+V ลงถูกที่
        if self._prev_app is not None:
            try:
                self._prev_app.activateWithOptions_(2)   # ignoringOtherApps
                time.sleep(0.15)
            except Exception:
                pass
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
