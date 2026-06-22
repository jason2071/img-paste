"""Radial image wheel (GTA weapon-wheel) — donut + thumbnails, transparent.

macOS: วาดด้วย AppKit NSWindow โปร่งจริง (เห็นแค่วงกลมลอย ไม่มีกล่องสี่เหลี่ยม).
donut แบ่ง 8 wedge มี gap คั่นชัด, แต่ละ wedge ใส่ thumbnail, hub กลาง = สลับ source.
ชี้เมาส์ -> wedge สว่าง, คลิก = เลือก -> copy image + paste. Esc/คลิกขวา = ยกเลิก.
non-macOS / ไม่มี AppKit -> fallback เป็น grid picker.

รันเป็น process แยก: python -m imgpaste.wheel
"""

from __future__ import annotations

import math
import os
import sys
import time

from . import config as cfg_mod
from . import paste, sound
from .clipboard import copy_image

# ---- geometry (3x3 grid, การ์ดสี่เหลี่ยมผืนผ้า, hub กลางเป็นการ์ดด้วย) ----
_W = 680
_CXY = _W / 2
_CARD_W = 134            # การ์ด portrait (สี่เหลี่ยมผืนผ้า)
_CARD_H = 184
_CARD_RAD = 14
_GAP = 16
_STEP_X = _CARD_W + _GAP
_STEP_Y = _CARD_H + _GAP
_CARD_SCALE_HOT = 1.12   # hover ขยายภาพขึ้นมา (ไม่ชนใบข้าง)
# 8 ช่องรอบ hub (gx, gy) — y ขึ้นบน; center (0,0) = hub
_GRID = [(-1, 1), (0, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (0, -1), (1, -1)]


# =========================================================
# pure helpers (unit-testable, ใช้ร่วม/test ได้)
# =========================================================
def slot_positions(n: int, radius: float, cx: float = _CXY, cy: float = _CXY):
    out = []
    for i in range(n):
        theta = math.radians(i * (360.0 / n))
        out.append((cx + radius * math.sin(theta), cy - radius * math.cos(theta)))
    return out


def slot_at_angle(angle_deg: float, n: int) -> int:
    return int(round(angle_deg / (360.0 / n))) % n


def angle_from_center(dx: float, dy: float) -> float:
    return (math.degrees(math.atan2(dx, dy))) % 360.0


def truncate_label(path: str, max_chars: int = 22) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem if len(stem) <= max_chars else stem[: max_chars - 1] + "…"


def images_in_dir(d: str, cfg: cfg_mod.Config, limit: int):
    if not os.path.isdir(d):
        return []
    items = []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for name in names:
        if cfg.is_image(name):
            p = os.path.join(d, name)
            try:
                items.append((os.path.getmtime(p), p))
            except OSError:
                pass
    items.sort(reverse=True)
    return [p for _, p in items[:limit]]


# =========================================================
# AppKit donut wheel (macOS)
# =========================================================
try:
    import objc
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyAccessory,
        NSPanel, NSView, NSColor, NSBezierPath, NSImage, NSShadow, NSScreen,
        NSGradient,
        NSFont, NSTimer, NSEvent, NSGraphicsContext,
        NSWindowStyleMaskBorderless, NSWindowStyleMaskNonactivatingPanel,
        NSBackingStoreBuffered, NSStatusWindowLevel,
        NSCompositingOperationSourceOver, NSEventTypeApplicationDefined,
        NSTrackingArea, NSTrackingMouseMoved, NSTrackingActiveAlways,
        NSTrackingInVisibleRect, NSForegroundColorAttributeName,
        NSFontAttributeName, NSShadowAttributeName,
    )
    from Foundation import (
        NSMakeRect, NSMakePoint, NSMakeSize, NSZeroRect, NSAffineTransform,
    )
    _HAS_APPKIT = True
except Exception:
    _HAS_APPKIT = False


if _HAS_APPKIT:

    def _rgba(r, g, b, a):
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)

    # ===== Themes (สลับผ่าน config wheel_theme) =====
    # key เหมือนกันทุกธีม; shadow_*_rgb optional (default ดำ)
    THEMES = {
        "floating_orbs": {
            "orbit_ring": (0.55, 0.55, 0.60, 0.18),
            "orb_border": (1.00, 1.00, 1.00, 0.55),
            "orb_border_hot": (0.98, 0.98, 1.00, 1.00),
            "orb_empty": (0.18, 0.19, 0.24, 0.65),
            "glow": (0.55, 0.65, 1.00, 0.45),
            "hub": (0.10, 0.10, 0.14, 0.82),
            "hub_hot": (0.14, 0.14, 0.20, 0.92),
            "hub_ring": (1.00, 1.00, 1.00, 0.22),
            "hub_ring_hot": (0.96, 0.96, 1.00, 0.70),
            "text": (1.00, 1.00, 1.00, 0.92),
            "sub": (0.75, 0.77, 0.90, 0.80),
            "shadow_orb_a": 0.28, "shadow_orb_a_hot": 0.42,
            "shadow_orb_blur": 18, "shadow_orb_blur_hot": 26,
            "shadow_hub_a": 0.35, "shadow_hub_blur": 22,
        },
        "aurora": {
            "orbit_ring": (0.20, 0.65, 0.50, 0.22),
            "orb_border": (0.85, 0.95, 0.90, 0.60),
            "orb_border_hot": (0.80, 1.00, 0.90, 1.00),
            "orb_empty": (0.08, 0.18, 0.14, 0.70),
            "glow": (0.00, 1.00, 0.67, 0.50),
            "hub": (0.06, 0.12, 0.10, 0.86),
            "hub_hot": (0.08, 0.18, 0.14, 0.94),
            "hub_ring": (0.40, 0.90, 0.65, 0.30),
            "hub_ring_hot": (0.20, 1.00, 0.70, 0.80),
            "text": (0.90, 1.00, 0.94, 0.95),
            "sub": (0.50, 0.85, 0.65, 0.75),
            "shadow_orb_a": 0.28, "shadow_orb_a_hot": 0.45,
            "shadow_orb_blur": 18, "shadow_orb_blur_hot": 28,
            "shadow_hub_a": 0.40, "shadow_hub_blur": 24,
            "shadow_hub_rgb": (0.0, 0.20, 0.10),
        },
        "ember": {
            "orbit_ring": (0.70, 0.45, 0.15, 0.20),
            "orb_border": (1.00, 0.85, 0.55, 0.65),
            "orb_border_hot": (1.00, 0.95, 0.75, 1.00),
            "orb_empty": (0.18, 0.12, 0.06, 0.68),
            "glow": (1.00, 0.72, 0.18, 0.50),
            "hub": (0.12, 0.08, 0.04, 0.86),
            "hub_hot": (0.18, 0.12, 0.05, 0.94),
            "hub_ring": (0.80, 0.55, 0.20, 0.30),
            "hub_ring_hot": (1.00, 0.80, 0.35, 0.85),
            "text": (1.00, 0.96, 0.88, 0.95),
            "sub": (0.90, 0.72, 0.45, 0.78),
            "shadow_orb_a": 0.32, "shadow_orb_a_hot": 0.48,
            "shadow_orb_blur": 18, "shadow_orb_blur_hot": 28,
            "shadow_hub_a": 0.42, "shadow_hub_blur": 24,
            "shadow_orb_rgb": (0.10, 0.05, 0.0),
            "shadow_hub_rgb": (0.08, 0.04, 0.0),
        },
        "void_mono": {
            "orbit_ring": (1.00, 1.00, 1.00, 0.12),
            "orb_border": (1.00, 1.00, 1.00, 0.50),
            "orb_border_hot": (1.00, 1.00, 1.00, 1.00),
            "orb_empty": (0.15, 0.15, 0.15, 0.70),
            "glow": (1.00, 1.00, 1.00, 0.35),
            "hub": (0.08, 0.08, 0.08, 0.90),
            "hub_hot": (0.14, 0.14, 0.14, 0.96),
            "hub_ring": (1.00, 1.00, 1.00, 0.18),
            "hub_ring_hot": (1.00, 1.00, 1.00, 0.85),
            "text": (1.00, 1.00, 1.00, 0.95),
            "sub": (0.80, 0.80, 0.80, 0.70),
            "shadow_orb_a": 0.35, "shadow_orb_a_hot": 0.55,
            "shadow_orb_blur": 20, "shadow_orb_blur_hot": 30,
            "shadow_hub_a": 0.45, "shadow_hub_blur": 26,
        },
        "lavender_glass": {
            "orbit_ring": (0.55, 0.40, 0.80, 0.22),
            "orb_border": (0.78, 0.72, 0.95, 0.62),
            "orb_border_hot": (0.92, 0.88, 1.00, 1.00),
            "orb_empty": (0.14, 0.10, 0.22, 0.68),
            "glow": (0.72, 0.50, 1.00, 0.48),
            "hub": (0.10, 0.07, 0.18, 0.86),
            "hub_hot": (0.15, 0.10, 0.26, 0.94),
            "hub_ring": (0.70, 0.55, 1.00, 0.28),
            "hub_ring_hot": (0.85, 0.72, 1.00, 0.82),
            "text": (0.96, 0.94, 1.00, 0.95),
            "sub": (0.72, 0.65, 0.90, 0.78),
            "shadow_orb_a": 0.32, "shadow_orb_a_hot": 0.50,
            "shadow_orb_blur": 18, "shadow_orb_blur_hot": 28,
            "shadow_hub_a": 0.45, "shadow_hub_blur": 24,
            "shadow_orb_rgb": (0.05, 0.0, 0.15),
            "shadow_hub_rgb": (0.04, 0.0, 0.12),
        },
    }

    _TH = THEMES.get(cfg_mod.load().wheel_theme, THEMES["aurora"])

    _C_ORBIT_RING = _rgba(*_TH["orbit_ring"])
    _C_ORB_RING = _rgba(*_TH["orb_border"])
    _C_ORB_HOT = _rgba(*_TH["orb_border_hot"])
    _C_ORB_EMPTY = _rgba(*_TH["orb_empty"])
    _C_GLOW = _rgba(*_TH["glow"])
    _C_HUB = _rgba(*_TH["hub"])
    _C_HUB_HOT = _rgba(*_TH["hub_hot"])
    _C_HUB_RING = _rgba(*_TH["hub_ring"])
    _C_HUB_RING_HOT = _rgba(*_TH["hub_ring_hot"])
    _C_TEXT = _rgba(*_TH["text"])
    _C_SUB = _rgba(*_TH["sub"])

    # shadow params (alpha/blur/สี tint) จากธีม
    _SH_ORB_A = _TH["shadow_orb_a"]
    _SH_ORB_A_HOT = _TH["shadow_orb_a_hot"]
    _SH_ORB_BLUR = _TH["shadow_orb_blur"]
    _SH_ORB_BLUR_HOT = _TH["shadow_orb_blur_hot"]
    _SH_HUB_A = _TH["shadow_hub_a"]
    _SH_HUB_BLUR = _TH["shadow_hub_blur"]
    _SH_ORB_RGB = _TH.get("shadow_orb_rgb", (0.0, 0.0, 0.0))
    _SH_HUB_RGB = _TH.get("shadow_hub_rgb", (0.0, 0.0, 0.0))

    def _oval(cx, cy, r):
        return NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(cx - r, cy - r, r * 2, r * 2))

    def _text(s, x, y, font, color, sub=False):
        attrs = {
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: color,
        }
        from Foundation import NSAttributedString
        astr = NSAttributedString.alloc().initWithString_attributes_(s, attrs)
        sz = astr.size()
        astr.drawAtPoint_(NSMakePoint(x - sz.width / 2, y - sz.height / 2))

    class WheelWindow(NSPanel):
        # nonactivating panel: ลอยรับ mouse ได้โดยไม่ขโมย focus จาก app ที่ user ใช้อยู่
        def canBecomeKeyWindow(self):
            return True

        def canBecomeMainWindow(self):
            return False

    class WheelView(NSView):
        def isFlipped(self):
            return False

        def acceptsFirstResponder(self):
            return True

        def acceptsFirstMouse_(self, _event):
            return True  # คลิกแรกติดเลย แม้ panel ยังไม่ active

        def drawRect_(self, _rect):
            ctrl = self.controller
            n = ctrl.slots
            kind, active = ctrl.active
            imgs = ctrl.images

            def card(i):
                hot = kind == "slot" and i == active
                gx, gy = _GRID[i]
                cx = _CXY + gx * _STEP_X
                cy = _CXY + gy * _STEP_Y
                sc = _CARD_SCALE_HOT if hot else 1.0
                w, h = _CARD_W * sc, _CARD_H * sc
                rad = _CARD_RAD * sc
                has = i < len(imgs)
                img = ctrl.thumb(imgs[i]) if has else None
                rect = NSMakeRect(cx - w / 2, cy - h / 2, w, h)
                rrect = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    rect, rad, rad)

                # base + shadow (boost ให้ลอยชัดบนพื้นมืด)
                NSGraphicsContext.saveGraphicsState()
                sh = NSShadow.alloc().init()
                a = max(_SH_ORB_A_HOT if hot else _SH_ORB_A, 0.40 if hot else 0.36)
                sh.setShadowColor_(_rgba(*_SH_ORB_RGB, a))
                sh.setShadowBlurRadius_(max(_SH_ORB_BLUR_HOT if hot else _SH_ORB_BLUR, 22))
                sh.setShadowOffset_(NSMakeSize(0, -5))
                sh.set()
                (NSColor.whiteColor() if has else _C_ORB_EMPTY).set()
                rrect.fill()
                NSGraphicsContext.restoreGraphicsState()

                # content: clip -> วาดรูป aspect-fill + gradient + ชื่อไฟล์ล่าง
                if img is not None:
                    NSGraphicsContext.saveGraphicsState()
                    rrect.addClip()
                    s = img.size().width or 1
                    scv = max(w / s, h / s)
                    fw, fh = w / scv, h / scv
                    frm = NSMakeRect((s - fw) / 2, (s - fh) / 2, fw, fh)
                    img.drawInRect_fromRect_operation_fraction_(
                        rect, frm, NSCompositingOperationSourceOver, 1.0)
                    # gradient ดำล่าง ให้ตัวหนังสืออ่านออก
                    strip = NSMakeRect(cx - w / 2, cy - h / 2, w, 42)
                    NSGradient.alloc().initWithStartingColor_endingColor_(
                        _rgba(0, 0, 0, 0.80), _rgba(0, 0, 0, 0.0)
                    ).drawInRect_angle_(strip, 90)
                    NSGraphicsContext.restoreGraphicsState()
                    _text(truncate_label(imgs[i], 18), cx, cy - h / 2 + 16,
                          NSFont.systemFontOfSize_(11), _rgba(1, 1, 1, 0.92))

                # glow + ขอบ
                if hot:
                    g = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                        NSMakeRect(cx - w / 2 - 4, cy - h / 2 - 4, w + 8, h + 8),
                        rad + 3, rad + 3)
                    g.setLineWidth_(1.5)
                    _C_GLOW.set()
                    g.stroke()
                rrect.setLineWidth_(3.0 if hot else 2.0)
                (_C_ORB_HOT if hot else _C_ORB_RING).set()
                rrect.stroke()

            # วาด tile ปกติก่อน แล้ว tile ที่ hover ทับบนสุด (zoom)
            cells = min(n, len(_GRID))
            hot_i = active if kind == "slot" else -1
            for i in range(cells):
                if i != hot_i:
                    card(i)
            if 0 <= hot_i < cells:
                card(hot_i)

            # ---- hub (dark glass) แบ่ง 2 โซน: บน=Capture, ล่าง=สลับ source ----
            cap_hot = kind == "capture"
            src_hot = kind == "center"
            NSGraphicsContext.saveGraphicsState()
            hsh = NSShadow.alloc().init()
            hsh.setShadowColor_(_rgba(*_SH_HUB_RGB, _SH_HUB_A))
            hsh.setShadowBlurRadius_(_SH_HUB_BLUR)
            hsh.setShadowOffset_(NSMakeSize(0, -4))
            hsh.set()
            hub_w, hub_h, hub_rad = _CARD_W, 136, 26
            hub_rect = NSMakeRect(_CXY - hub_w / 2, _CXY - hub_h / 2, hub_w, hub_h)
            hub = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                hub_rect, hub_rad, hub_rad)
            _C_HUB.set()
            hub.fill()
            NSGraphicsContext.restoreGraphicsState()
            # hover highlight ครึ่งที่ชี้ (clip ใน hub)
            if cap_hot or src_hot:
                NSGraphicsContext.saveGraphicsState()
                hub.addClip()
                _C_HUB_HOT.set()
                hy = _CXY if cap_hot else _CXY - hub_h / 2
                NSBezierPath.fillRect_(
                    NSMakeRect(_CXY - hub_w / 2, hy, hub_w, hub_h / 2))
                NSGraphicsContext.restoreGraphicsState()
            # เส้นคั่น 2 โซน
            sep = NSBezierPath.bezierPath()
            sep.setLineWidth_(1.0)
            sep.moveToPoint_(NSMakePoint(_CXY - hub_w / 2 + 14, _CXY))
            sep.lineToPoint_(NSMakePoint(_CXY + hub_w / 2 - 14, _CXY))
            _C_HUB_RING.set()
            sep.stroke()
            hub.setLineWidth_(2.0 if (cap_hot or src_hot) else 1.5)
            (_C_HUB_RING_HOT if (cap_hot or src_hot) else _C_HUB_RING).set()
            hub.stroke()
            # บน: Capture
            _text("📷 Capture", _CXY, _CXY + 34,
                  NSFont.boldSystemFontOfSize_(15), _C_TEXT)
            # ล่าง: source toggle
            _text(ctrl.source_label(), _CXY, _CXY - 24,
                  NSFont.boldSystemFontOfSize_(18), _C_TEXT)
            _text("⇄ สลับ", _CXY, _CXY - 48,
                  NSFont.systemFontOfSize_(12), _C_SUB, sub=True)

        # ---- events ----
        @objc.python_method
        def _hit(self, event):
            loc = self.convertPoint_fromView_(event.locationInWindow(), None)
            # ช่องกลาง (hub) = สี่เหลี่ยม แบ่ง 2 โซน: บน=capture, ล่าง=สลับ source
            if abs(loc.x - _CXY) <= _STEP_X / 2 and abs(loc.y - _CXY) <= _STEP_Y / 2:
                return ("capture", -1) if loc.y > _CXY else ("center", -1)
            # pointer อยู่ในช่องไหนของ grid (ช่องสี่เหลี่ยมผืนผ้า)
            cells = min(self.controller.slots, len(_GRID))
            for i in range(cells):
                gx, gy = _GRID[i]
                cx = _CXY + gx * _STEP_X
                cy = _CXY + gy * _STEP_Y
                if abs(loc.x - cx) <= _STEP_X / 2 and abs(loc.y - cy) <= _STEP_Y / 2:
                    return ("slot", i)
            return ("none", -1)

        def mouseMoved_(self, event):
            a = self._hit(event)
            if a != self.controller.active:
                prev = self.controller.active
                self.controller.active = a
                self.setNeedsDisplay_(True)
                # tick ตอนเลื่อนเข้าช่องใหม่ (slot/capture); ไม่เล่นตอน none/center
                if a[0] in ("slot", "capture") and a != prev and self.controller.cfg.sound:
                    sound.play("hover")

        def mouseDown_(self, event):
            kind, idx = self._hit(event)
            if kind == "capture":
                self.controller.capture()
            elif kind == "center":
                self.controller.toggle_source()
                self.setNeedsDisplay_(True)
            elif kind == "slot":
                self.controller.select(idx)
            else:  # คลิกโซนโปร่งนอกวง = ยกเลิก (Esc อาจไม่มาเพราะ panel ไม่ถือ key)
                self.controller.cancel()

        def rightMouseDown_(self, event):
            self.controller.cancel()

        def keyDown_(self, event):
            if event.keyCode() == 53:  # Esc
                self.controller.cancel()

    class AppKitWheel:
        def __init__(self):
            self.cfg = cfg_mod.load()
            self.slots = max(1, int(self.cfg.wheel_slots))
            self.source = 0
            self.selected = None
            self.do_capture = False
            self.active = ("none", -1)
            self._thumbs = {}
            self.images = self._images_now()
            self._preload()

            scr = NSScreen.mainScreen().frame()
            x = scr.origin.x + (scr.size.width - _W) / 2
            y = scr.origin.y + (scr.size.height - _W) / 2
            self.win = WheelWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, _W, _W),
                NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
                NSBackingStoreBuffered, False)
            self.win.setOpaque_(False)
            self.win.setBackgroundColor_(NSColor.clearColor())
            self.win.setLevel_(NSStatusWindowLevel)
            self.win.setHasShadow_(False)
            self.win.setIgnoresMouseEvents_(False)
            self.win.setAcceptsMouseMovedEvents_(True)
            self.win.setFloatingPanel_(True)
            self.win.setBecomesKeyOnlyIfNeeded_(True)

            self.view = WheelView.alloc().initWithFrame_(NSMakeRect(0, 0, _W, _W))
            self.view.controller = self
            self.win.setContentView_(self.view)
            area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.view.bounds(),
                NSTrackingMouseMoved | NSTrackingActiveAlways | NSTrackingInVisibleRect,
                self.view, None)
            self.view.addTrackingArea_(area)

        def _source_dir(self):
            dirs = self.cfg.dirs
            return dirs[self.source] if self.source < len(dirs) else dirs[0]

        def source_label(self):
            return os.path.basename(self._source_dir().rstrip("/")) or self._source_dir()

        def _images_now(self):
            return images_in_dir(self._source_dir(), self.cfg, self.slots)

        def thumb(self, path):
            """คืน thumbnail ที่ pre-render เป็น bitmap เล็ก (cache) — วาดเร็วทุก frame."""
            if path not in self._thumbs:
                src = NSImage.alloc().initWithContentsOfFile_(path)
                self._thumbs[path] = self._render_small(src) if src else None
            return self._thumbs[path]

        def _render_small(self, src):
            s = int(max(_CARD_W, _CARD_H) * _CARD_SCALE_HOT) + 4
            isz = src.size()
            side = min(isz.width, isz.height) or 1
            frm = NSMakeRect((isz.width - side) / 2, (isz.height - side) / 2,
                             side, side)
            out = NSImage.alloc().initWithSize_(NSMakeSize(s, s))
            out.lockFocus()
            src.drawInRect_fromRect_operation_fraction_(
                NSMakeRect(0, 0, s, s), frm, NSCompositingOperationSourceOver, 1.0)
            out.unlockFocus()
            return out

        def _preload(self):
            for p in self.images:
                self.thumb(p)

        def toggle_source(self):
            self.source = (self.source + 1) % max(1, len(self.cfg.dirs))
            self.active = ("none", -1)
            self.images = self._images_now()
            self._preload()
            if self.cfg.sound:
                sound.play("toggle")

        def select(self, idx):
            if idx < len(self.images):
                self.selected = self.images[idx]
            self._stop()

        def cancel(self):
            self.selected = None
            self._stop()

        def capture(self):
            self.do_capture = True       # run() จะเปิด cropper editor หลังปิด wheel
            self._stop()

        def _stop(self):
            self.win.orderOut_(None)
            app = NSApplication.sharedApplication()
            app.stop_(None)
            ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSEventTypeApplicationDefined, NSMakePoint(0, 0), 0, 0, 0, None, 0, 0, 0)
            app.postEvent_atStart_(ev, True)

        def _mouse_over_win(self):
            try:
                p = NSEvent.mouseLocation()
                f = self.win.frame()
                return (f.origin.x <= p.x <= f.origin.x + f.size.width and
                        f.origin.y <= p.y <= f.origin.y + f.size.height)
            except Exception:
                return True

        def run(self):
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            # โชว์โดยไม่ activate ตัวเอง -> app ที่ user focus อยู่ (แชท) ยังถือ focus
            self.win.orderFrontRegardless()
            self.win.makeFirstResponder_(self.view)

            # nonactivating panel ไม่รับ keyDown -> global Esc listener
            # (gate ด้วย mouse เหนือวงล้อ: Esc ที่ app อื่นไม่ยกเลิก)
            esc_listener = None
            try:
                from pynput import keyboard as _pk
                from PyObjCTools import AppHelper

                def _gk(key):
                    if key == _pk.Key.esc and self._mouse_over_win():
                        AppHelper.callAfter(self.cancel)
                esc_listener = _pk.Listener(on_press=_gk)
                esc_listener.start()
            except Exception:
                pass

            auto = os.environ.get("IMGPASTE_AUTOPICK")
            if auto is not None and auto.isdigit():
                NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                    0.9, False, lambda t: self.select(int(auto)))

            app.run()

            if esc_listener is not None:
                try:
                    esc_listener.stop()
                except Exception:
                    pass

            if self.do_capture:          # hub บน -> เปิด cropper (จับภาพ + editor)
                from . import _exec
                try:
                    _exec.spawn(["cropper", "--capture"])
                except Exception:
                    pass
                return
            if not self.selected:
                return
            time.sleep(self.cfg.paste_delay)
            copy_image(self.selected)
            # ตอนเลือกไม่เล่นเสียง (มีแต่ tick ตอน hover)
            # paste จาก subprocess สะอาด — เลี่ยง double-key (Listener+NSApp.run)
            if self.cfg.auto_paste and paste.available():
                paste.paste_detached()


def run():
    if sys.platform == "darwin" and _HAS_APPKIT:
        AppKitWheel().run()
    else:
        from . import picker
        picker.run()


if __name__ == "__main__":
    run()
