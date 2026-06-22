"""Crop & annotate editor — AppKit (PyObjC).

NSPanel โปร่งใส ลอยกลางจอ (เหมือน wheel): ภาพ + กรอบฟ้า + toolbar 2 pill ลอย,
ไม่มีกล่องดำ, ไม่ขโมย focus (Send paste ลงตรง). crop / วาด rect/oval/line /
เลือก stroke+สี preset / Save / Send (copy + auto Cmd+V).
รันเป็น process แยก: python -m imgpaste.cropper [path] [--capture]
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw

from . import config as cfg_mod
from . import paste
from .clipboard import copy_image

# ---- palette (hex) ----
_TB_BG = "#ffffff"
_BORDER = "#e7e8ee"
_ICON = "#3c3c43"
_ACTIVE_BG = "#dbe7ff"
_ACTIVE_FG = "#0a6cff"
_ACTIVE_RING = "#9bc0ff"
_HOVER_BG = "#f1f2f7"
_DONE_BG = "#34c759"
_CANCEL = "#ff3b30"
_SEP = "#e3e3e8"
_BLUE = "#3b82f6"
_SWATCHES = ["#ff3b30", "#ff9f0a", "#34c759", "#0a84ff", "#bf5af2",
             "#ffffff", "#000000"]
_STROKES = [2, 5, 9]
# geometry
_MARGIN = 22
_GAP = 16
_TB_H = 48
_PILL_R = 16
_BW, _SEPW, _PAD = 36, 15, 13
_FLY_H = 42
_MAX_W, _MAX_H = 1100, 720
_TOOLS = ["undo", "redo", "|", "rect", "oval", "line"]
_ACTIONS = ["close", "copy", "save", "done"]


def _capture_region() -> str | None:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        subprocess.run(["screencapture", "-i", "-x", tmp.name], check=False)
    except Exception:
        pass
    if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
        return tmp.name
    try:                       # user cancel / empty -> ลบ temp ทิ้ง
        os.unlink(tmp.name)
    except OSError:
        pass
    return None


try:
    import objc
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyAccessory, NSPanel,
        NSView, NSColor, NSBezierPath, NSImage, NSScreen, NSEvent,
        NSGraphicsContext, NSSavePanel, NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel, NSBackingStoreBuffered,
        NSStatusWindowLevel, NSCompositingOperationSourceOver,
        NSEventTypeApplicationDefined,
    )
    from Foundation import (
        NSMakeRect, NSMakePoint, NSMakeSize, NSZeroRect, NSData,
        NSAffineTransform,
    )
    _HAS_APPKIT = True
except Exception:
    _HAS_APPKIT = False


if _HAS_APPKIT:

    def _c(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)

    def _pil_to_ns(pil):
        buf = io.BytesIO()
        pil.convert("RGBA").save(buf, "PNG")
        raw = buf.getvalue()
        return NSImage.alloc().initWithData_(
            NSData.dataWithBytes_length_(raw, len(raw)))

    def _rr(x1, y1, x2, y2, r):
        return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x1, y1, x2 - x1, y2 - y1), r, r)

    def _icon(name, x, y, col, w=2.0):
        """วาด vector icon (โค้ด coords แบบ y-down ทับ transform flip)."""
        c = _c(col)
        ctx = NSGraphicsContext.currentContext()
        ctx.saveGraphicsState()
        t = NSAffineTransform.transform()
        t.translateXBy_yBy_(x, y)
        t.scaleXBy_yBy_(1.0, -1.0)
        t.concat()

        def L(*pts):
            p = NSBezierPath.bezierPath()
            p.setLineWidth_(w)
            p.setLineCapStyle_(1)
            p.setLineJoinStyle_(1)
            p.moveToPoint_(NSMakePoint(pts[0], pts[1]))
            for i in range(2, len(pts), 2):
                p.lineToPoint_(NSMakePoint(pts[i], pts[i + 1]))
            c.set()
            p.stroke()

        c.set()
        if name == "rect":
            p = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(-7, -6, 14, 12), 3, 3)
            p.setLineWidth_(w)
            p.stroke()
        elif name == "oval":
            p = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(-7, -7, 14, 14))
            p.setLineWidth_(w)
            p.stroke()
        elif name == "line":
            L(-7, 6, 7, -6)
        elif name == "close":
            L(-6, -6, 6, 6)
            L(-6, 6, 6, -6)
        elif name == "check":
            L(-6, 1, -2, 5, 7, -6)
        elif name == "copy":
            for (a, b, cc, d) in [(-7, -7, 2, 2), (-2, -2, 7, 7)]:
                p = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    NSMakeRect(a, b, cc - a, d - b), 2, 2)
                p.setLineWidth_(w)
                p.stroke()
        elif name == "save":
            L(0, -7, 0, 3)
            L(-4, -1, 0, 3, 4, -1)
            L(-6, 7, 6, 7)
        elif name == "undo":
            arc = NSBezierPath.bezierPath()
            arc.setLineWidth_(w)
            arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
                NSMakePoint(0, 1), 7, 20, 270)
            arc.stroke()
            L(-7, -3, -6, -7, -2, -6)
        elif name == "redo":
            arc = NSBezierPath.bezierPath()
            arc.setLineWidth_(w)
            arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
                NSMakePoint(0, 1), 7, -90, 200)
            arc.stroke()
            L(7, -3, 6, -7, 2, -6)
        ctx.restoreGraphicsState()

    class CropPanel(NSPanel):
        def canBecomeKeyWindow(self):
            return True

    class CropView(NSView):
        def isFlipped(self):
            return False

        def acceptsFirstResponder(self):
            return True

        def acceptsFirstMouse_(self, _e):
            return True

        def drawRect_(self, _r):
            self.ctrl._draw(self)

        def mouseDown_(self, e):
            self.ctrl._md(self._pt(e))

        def mouseDragged_(self, e):
            self.ctrl._mg(self._pt(e))

        def mouseUp_(self, e):
            self.ctrl._mu(self._pt(e))

        def mouseMoved_(self, e):
            self.ctrl._mm(self._pt(e))

        def keyDown_(self, e):
            if e.keyCode() == 53:
                self.ctrl._on_escape()

        @objc.python_method
        def _pt(self, e):
            p = self.convertPoint_fromView_(e.locationInWindow(), None)
            return (p.x, p.y)

    class Cropper:
        def __init__(self, path=None, capture=False):
            self.cfg = cfg_mod.load()
            if capture:
                c = _capture_region()
                if c:
                    path = c
            self.orig = None            # PIL
            self.nsimg = None
            self.scale = 1.0
            self.tool = None
            self.color = "#ff3b30"
            self.width = 5
            self.shapes = []            # (tool,x0,y0,x1,y1,color,width) image-local y-down
            self.redo = []
            self.fly_open = False
            self.fly_btn = None
            self._drag = None
            self._hover = None

            if path and os.path.isfile(path):
                self._load_pil(path)

            self.app = NSApplication.sharedApplication()
            self.app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            self.panel = CropPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, 400, 300),
                NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
                NSBackingStoreBuffered, False)
            self.panel.setOpaque_(False)
            self.panel.setBackgroundColor_(NSColor.clearColor())
            self.panel.setLevel_(NSStatusWindowLevel)
            self.panel.setHasShadow_(False)
            self.panel.setFloatingPanel_(True)
            self.panel.setBecomesKeyOnlyIfNeeded_(True)
            self.panel.setAcceptsMouseMovedEvents_(True)
            self.view = CropView.alloc().initWithFrame_(NSMakeRect(0, 0, 400, 300))
            self.view.ctrl = self
            self.panel.setContentView_(self.view)
            self._relayout()

            # nonactivating panel ไม่รับ keyDown (ไม่มี focus) -> global Esc listener
            # gate ด้วย mouse อยู่เหนือ panel: Esc ที่ app อื่นจะไม่ปิด cropper
            self._esc_listener = None
            try:
                from pynput import keyboard as _pk
                from PyObjCTools import AppHelper

                def _gk(key):
                    if key == _pk.Key.esc and self._mouse_over_panel():
                        AppHelper.callAfter(self._on_escape)
                self._esc_listener = _pk.Listener(on_press=_gk)
                self._esc_listener.start()
            except Exception:
                pass

        def _mouse_over_panel(self):
            try:
                p = NSEvent.mouseLocation()       # screen coords (y-up)
                f = self.panel.frame()
                return (f.origin.x <= p.x <= f.origin.x + f.size.width and
                        f.origin.y <= p.y <= f.origin.y + f.size.height)
            except Exception:
                return True

        # ---------- image ----------
        def _load_pil(self, path):
            try:
                self.orig = Image.open(path).convert("RGBA")
            except Exception:
                self.orig = None
                return
            if self.orig.width == 0 or self.orig.height == 0:
                self.orig = None        # ภาพ degenerate -> กัน ZeroDivision
                return
            self.shapes.clear()
            self.redo.clear()
            self.fly_open = False
            self.tool = None
            self.nsimg = _pil_to_ns(self.orig)
            self.scale = min(_MAX_W / self.orig.width,
                             _MAX_H / self.orig.height, 1.0)

        # ---------- layout (y-up panel coords) ----------
        def _relayout(self):
            if self.orig is None:
                return
            dw = max(1, int(self.orig.width * self.scale))
            dh = max(1, int(self.orig.height * self.scale))
            tools_w = _PAD * 2 + 5 * _BW + 1 * _SEPW
            act_w = _PAD * 2 + 4 * _BW
            tbar_w = tools_w + _GAP + act_w
            fly_w = 14 * 2 + len(_STROKES) * 30 + 18 + len(_SWATCHES) * 28
            fly_on = self.fly_open
            pw = max(dw + 2 * _MARGIN, tbar_w + 24)
            ph = (_MARGIN + dh + _TB_H
                  + ((7 + _FLY_H) if fly_on else 0) + _MARGIN)
            self._pw, self._ph = pw, ph
            self._dw, self._dh = dw, dh
            self._img = (round((pw - dw) / 2), ph - _MARGIN - dh, dw, dh)
            tb_y = self._img[1] - _TB_H
            tools_x = round((pw - tbar_w) / 2)
            act_x = tools_x + tools_w + _GAP
            self._tb_y = tb_y
            self._tools_rect = (tools_x, tb_y, tools_w, _TB_H)
            self._act_rect = (act_x, tb_y, act_w, _TB_H)
            # button hit-regions
            self._btns = []
            self._layout_pill(tools_x, tb_y, _TOOLS)
            self._layout_pill(act_x, tb_y, _ACTIONS)
            # flyout
            self._fly = []
            self._fly_w = fly_w
            if fly_on:
                bx = self._btn_cx(self.fly_btn) or (pw / 2)
                fx = min(pw - fly_w - 6, max(6, bx - fly_w / 2))
                fy = tb_y - 7 - _FLY_H
                self._fly_rect = (fx, fy, fly_w, _FLY_H)
                self._arrow_x = bx - fx
                self._layout_fly(fx, fy)
            else:
                self._fly_rect = None
            # apply panel size — anchor top-left เสมอหลังวางครั้งแรก (ไม่กระโดด)
            if getattr(self, "_placed", False):
                cur = self.panel.frame()
                x = cur.origin.x
                y = cur.origin.y + cur.size.height - ph     # คง top edge
            else:
                scr = NSScreen.mainScreen().frame()
                x = scr.origin.x + (scr.size.width - pw) / 2
                y = scr.origin.y + (scr.size.height - ph) / 2
            self.panel.setFrame_display_(NSMakeRect(x, y, pw, ph), True)
            self.view.setFrame_(NSMakeRect(0, 0, pw, ph))
            self._placed = True
            self.view.setNeedsDisplay_(True)

        def _layout_pill(self, px, py, specs):
            x = px + _PAD
            for s in specs:
                if s == "|":
                    x += _SEPW
                else:
                    # pill จริงสูง _TB_H-2 (fill ถึง y+h-2) -> จัด button กึ่งกลาง pill
                    y0 = py + (_TB_H - 2 - 36) / 2
                    self._btns.append((s, x, y0, x + _BW, y0 + 36))
                    x += _BW

        def _btn_cx(self, bid):
            for b in self._btns:
                if b[0] == bid:
                    return (b[1] + b[3]) / 2
            return None

        def _layout_fly(self, fx, fy):
            x = fx + 14
            cy = fy + _FLY_H / 2
            for px in _STROKES:
                self._fly.append(("stroke", px, x, x + 30, cy))
                x += 30
            self._fly.append(("sepf", None, x + 9, x + 9, cy))
            x += 18
            for col in _SWATCHES:
                self._fly.append(("color", col, x, x + 28, cy))
                x += 28

        # ---------- draw ----------
        def _draw(self, view):
            NSColor.clearColor().set()
            NSBezierPath.fillRect_(view.bounds())
            if self.orig is None:
                return
            ix, iy, iw, ih = self._img
            self.nsimg.drawInRect_fromRect_operation_fraction_(
                NSMakeRect(ix, iy, iw, ih), NSZeroRect,
                NSCompositingOperationSourceOver, 1.0)
            # shapes (image-local y-down -> view y-up)
            for s in self.shapes:
                self._draw_shape(s, ix, iy + ih)
            if self._drag is not None:
                self._draw_shape(self._drag, ix, iy + ih)
            # blue selection border
            _c(_BLUE).set()
            b = NSBezierPath.bezierPathWithRect_(NSMakeRect(ix + 1, iy + 1, iw - 2, ih - 2))
            b.setLineWidth_(2)
            b.stroke()
            # pills
            self._draw_pill(self._tools_rect, _TOOLS)
            self._draw_pill(self._act_rect, _ACTIONS)
            if self._fly_rect is not None:
                self._draw_fly()

        def _draw_shape(self, s, ix, itop):
            tool, x0, y0, x1, y1, col, w = s
            sc = self.scale
            X0, X1 = ix + x0 * sc, ix + x1 * sc
            Y0, Y1 = itop - y0 * sc, itop - y1 * sc     # full-res -> display, flip y
            _c(col).set()
            if tool == "line":
                p = NSBezierPath.bezierPath()
                p.setLineWidth_(w)
                p.setLineCapStyle_(1)
                p.moveToPoint_(NSMakePoint(X0, Y0))
                p.lineToPoint_(NSMakePoint(X1, Y1))
                p.stroke()
            else:
                rect = NSMakeRect(min(X0, X1), min(Y0, Y1),
                                  abs(X1 - X0), abs(Y1 - Y0))
                p = (NSBezierPath.bezierPathWithOvalInRect_(rect) if tool == "oval"
                     else NSBezierPath.bezierPathWithRect_(rect))
                p.setLineWidth_(w)
                p.stroke()

        def _pill_bg(self, rect):
            x, y, w, h = rect
            _c(_TB_BG).set()
            _rr(x, y, x + w, y + h - 2, _PILL_R).fill()
            _c(_BORDER).set()
            pp = _rr(x, y, x + w, y + h - 2, _PILL_R)
            pp.setLineWidth_(1)
            pp.stroke()

        def _draw_pill(self, rect, specs):
            self._pill_bg(rect)
            has = self.orig is not None
            for b in self._btns:
                bid, x0, y0, x1, y1 = b
                if bid not in specs:
                    continue
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                active = (bid in ("rect", "oval", "line")
                          and has and self.tool == bid)
                if bid == "done":
                    _c(_DONE_BG).set()
                    _rr(cx - 16, cy - 14, cx + 16, cy + 14, 10).fill()
                    _icon("check", cx, cy, "#ffffff")
                    continue
                if active:
                    _c(_ACTIVE_BG).set()
                    _rr(cx - 16, cy - 14, cx + 16, cy + 14, 9).fill()
                    _c(_ACTIVE_RING).set()
                    rp = _rr(cx - 16, cy - 14, cx + 16, cy + 14, 9)
                    rp.setLineWidth_(1)
                    rp.stroke()
                elif self._hover == bid:
                    _c(_HOVER_BG).set()
                    _rr(cx - 16, cy - 14, cx + 16, cy + 14, 9).fill()
                col = _CANCEL if bid == "close" else (_ACTIVE_FG if active else _ICON)
                _icon(bid, cx, cy, col)

        def _draw_fly(self):
            fx, fy, fw, fh = self._fly_rect
            cy = fy + fh / 2
            # arrow
            ax = fx + max(14, min(fw - 14, self._arrow_x))
            _c(_TB_BG).set()
            ar = NSBezierPath.bezierPath()
            ar.moveToPoint_(NSMakePoint(ax - 7, fy + fh - 1))
            ar.lineToPoint_(NSMakePoint(ax + 7, fy + fh - 1))
            ar.lineToPoint_(NSMakePoint(ax, fy + fh + 7))
            ar.closePath()
            ar.fill()
            self._pill_bg((fx, fy, fw, fh + 4))
            _c(_TB_BG).set()
            ar.fill()
            for it in self._fly:
                kind, key, x0, x1, _cy = it
                cx = (x0 + x1) / 2
                if kind == "sepf":
                    _c(_SEP).set()
                    p = NSBezierPath.bezierPath()
                    p.setLineWidth_(1)
                    p.moveToPoint_(NSMakePoint(x0, cy - 9))
                    p.lineToPoint_(NSMakePoint(x0, cy + 9))
                    p.stroke()
                elif kind == "stroke":
                    r = {2: 3, 5: 5, 9: 8}[key]
                    if key == self.width:
                        _c(_ACTIVE_RING).set()
                        rp = NSBezierPath.bezierPathWithOvalInRect_(
                            NSMakeRect(cx - r - 4, cy - r - 4, (r + 4) * 2, (r + 4) * 2))
                        rp.setLineWidth_(2)
                        rp.stroke()
                    _c(_ICON).set()
                    NSBezierPath.bezierPathWithOvalInRect_(
                        NSMakeRect(cx - r, cy - r, r * 2, r * 2)).fill()
                elif kind == "color":
                    sel = key.lower() == self.color.lower()
                    _c(key).set()
                    _rr(cx - 10, cy - 10, cx + 10, cy + 10, 5).fill()
                    _c("#000000" if sel else "#d0d0d6").set()
                    rp = _rr(cx - 10, cy - 10, cx + 10, cy + 10, 5)
                    rp.setLineWidth_(2 if sel else 1)
                    rp.stroke()

        # ---------- hit / mouse ----------
        def _btn_at(self, x, y):
            for b in self._btns:
                if b[1] <= x <= b[3] and b[2] <= y <= b[4]:
                    return b[0]
            return None

        def _fly_at(self, x, y):
            if self._fly_rect is None:
                return None
            fx, fy, fw, fh = self._fly_rect
            if not (fx <= x <= fx + fw and fy <= y <= fy + fh):
                return None
            for it in self._fly:
                if it[0] != "sepf" and it[2] <= x <= it[3]:
                    return it
            return ("none",)

        def _in_img(self, x, y):
            ix, iy, iw, ih = self._img
            return ix <= x <= ix + iw and iy <= y <= iy + ih

        def _md(self, pt):
            x, y = pt
            f = self._fly_at(x, y)
            if f is not None:
                if f[0] == "stroke":
                    self.width = f[1]; self._refresh()
                elif f[0] == "color":
                    self.color = f[1]; self._refresh()
                return
            bid = self._btn_at(x, y)
            if bid:
                self._dispatch(bid)
                return
            if self._in_img(x, y) and self.tool is not None:
                self._start = pt
                self._drag = (self.tool, self._lx(x), self._ly(y),
                              self._lx(x), self._ly(y), self.color, self.width)
                self.view.setNeedsDisplay_(True)

        def _mg(self, pt):
            if getattr(self, "_start", None) is None or self._drag is None:
                return
            x, y = pt
            self._drag = (self._drag[0], self._drag[1], self._drag[2],
                          self._lx(x), self._ly(y), self.color, self.width)
            self.view.setNeedsDisplay_(True)

        def _mu(self, pt):
            if getattr(self, "_start", None) is None:
                return
            self._start = None
            if self._drag is not None:
                _, x0, y0, x1, y1, _c2, _w = self._drag
                if abs(x1 - x0) > 2 or abs(y1 - y0) > 2:
                    self.shapes.append(self._drag)
                    self.redo.clear()
                self._drag = None
            self.view.setNeedsDisplay_(True)

        def _mm(self, pt):
            bid = self._btn_at(*pt)
            if bid != self._hover:
                self._hover = bid
                self.view.setNeedsDisplay_(True)

        def _lx(self, x):
            return (x - self._img[0]) / self.scale

        def _ly(self, y):
            ix, iy, iw, ih = self._img
            return ((iy + ih) - y) / self.scale

        # ---------- actions ----------
        def _dispatch(self, bid):
            {"undo": self._undo, "redo": self._do_redo,
             "rect": lambda: self._set_tool("rect"),
             "oval": lambda: self._set_tool("oval"),
             "line": lambda: self._set_tool("line"),
             "close": self._on_escape, "copy": self._copy_only,
             "save": self._save, "done": self._send}[bid]()

        def _set_tool(self, name):
            if self.orig is None:
                return
            if self.tool == name and self.fly_open:
                self.fly_open = False        # คลิกซ้ำ -> ปิด submenu
            else:
                self.tool = name
                self.fly_btn = name
                self.fly_open = True
            self._refresh()

        def _undo(self):
            if self.shapes:
                self.redo.append(self.shapes.pop())
                self.view.setNeedsDisplay_(True)

        def _do_redo(self):
            if self.redo:
                self.shapes.append(self.redo.pop())
                self.view.setNeedsDisplay_(True)

        def _refresh(self):
            self._relayout()

        def _on_escape(self):
            self._stop()

        def _stop(self):
            if getattr(self, "_stopping", False):
                return            # กันเรียกซ้ำ (keyDown + global Esc listener)
            self._stopping = True
            if self._esc_listener is not None:
                try:
                    self._esc_listener.stop()
                except Exception:
                    pass
                self._esc_listener = None
            self.panel.orderOut_(None)
            self.app.stop_(None)
            ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSEventTypeApplicationDefined, NSMakePoint(0, 0), 0, 0, 0, None,
                0, 0, 0)
            self.app.postEvent_atStart_(ev, True)

        # ---------- export ----------
        def _flatten(self):
            img = self.orig.copy()
            d = ImageDraw.Draw(img)
            for s in self.shapes:
                t, x0, y0, x1, y1, col, w = s
                w = max(1, int(round(w)))
                if t == "line":
                    d.line([x0, y0, x1, y1], fill=col, width=w)
                else:
                    box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
                    if t == "rect":
                        d.rectangle(box, outline=col, width=w)
                    else:
                        d.ellipse(box, outline=col, width=w)
            return img

        def _copy_to_clipboard(self):
            """flatten -> temp PNG -> clipboard -> ลบ temp (copy_image อ่าน sync)."""
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            try:
                self._flatten().save(tmp.name)
                copy_image(tmp.name)
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

        def _save(self):
            if self.orig is None:
                return
            sp = NSSavePanel.savePanel()
            sp.setNameFieldStringValue_(
                "imgpaste-" + time.strftime("%Y%m%d-%H%M%S") + ".png")
            # accessory+nonactivating -> ต้อง activate ให้ dialog ขึ้นหน้า/รับ key
            self.app.activateIgnoringOtherApps_(True)
            if sp.runModal() == 1:
                self._flatten().convert("RGB").save(sp.URL().path())
                self._stop()      # เซฟเสร็จ -> ปิดหน้าต่าง

        def _copy_only(self):
            if self.orig is None:
                return
            self._copy_to_clipboard()

        def _send(self):
            if self.orig is None:
                return
            self._copy_to_clipboard()
            self._stop()
            time.sleep(self.cfg.paste_delay)
            if paste.available():
                paste.paste()    # focus เดิมอยู่แล้ว (nonactivating panel)

        # ---------- run ----------
        def run(self):
            if self.orig is None:
                self._stop()     # กัน pynput listener ค้างตอนโหลดภาพไม่สำเร็จ
                return
            self.panel.orderFrontRegardless()
            self.panel.makeFirstResponder_(self.view)
            self.app.run()


def run(path=None, capture=False):
    if sys.platform == "darwin" and _HAS_APPKIT:
        Cropper(path, capture).run()
    else:
        sys.stderr.write("cropper: ต้องใช้ macOS + pyobjc\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    cap = "--capture" in args
    files = [a for a in args if not a.startswith("-")]
    run(files[0] if files else None, cap)
