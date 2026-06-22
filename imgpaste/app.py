"""TrayApp — orchestrate menu + hotkeys + shake + image wheel.

เมนูบาร์ launcher: capture region, เปิด image wheel, mouse-shake trigger.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time

import pystray
from pystray import Menu, MenuItem as Item

from . import config as cfg_mod
from . import hotkeys, icon, sound
from . import _exec
from .shake import ShakeDetector
from .shake import available as shake_available


def _enable_macos_template_icon() -> None:
    """ทำให้ menu-bar icon เป็น template image -> macOS auto-tint ขาว/ดำ
    ตามธีมระบบ เข้ากับ icon ตัวอื่นบน menu bar (แทนที่จะโชว์สีดิบ).

    pystray ไม่รองรับ template โดยตรง จึง wrap _assert_image ให้ตั้ง flag
    หลังสร้าง NSImage.
    """
    if sys.platform != "darwin":
        return
    try:
        from pystray import _darwin
    except Exception:
        return
    _orig = _darwin.Icon._assert_image

    def _assert_image(self):
        _orig(self)
        img = getattr(self, "_icon_image", None)
        if img is not None:
            img.setTemplate_(True)

    _darwin.Icon._assert_image = _assert_image


_enable_macos_template_icon()


class TrayApp:
    def __init__(self):
        self.cfg = cfg_mod.load()
        self.icon = pystray.Icon(
            "imgpaste",
            icon.make_icon(),
            "SnapPaste",
            menu=self._build_menu(),
        )
        self.shake = ShakeDetector(
            self._open_wheel, sensitivity=self.cfg.shake_sensitivity
        )
        self._wheel_proc: subprocess.Popen | None = None
        self._wheel_last = 0.0

    # ---- toggles ----
    def _toggle_sound(self, icon=None, item=None) -> None:
        self.cfg.sound = not self.cfg.sound
        cfg_mod.save(self.cfg)
        if self.cfg.sound:
            sound.play("toggle")

    # ---- capture region (เหมือน Cmd+Shift+4) -> เปิด preview editor (ยังไม่วาง) ----
    def _capture_screen(self, icon=None, item=None) -> None:
        threading.Thread(target=self._do_capture, daemon=True).start()

    def _do_capture(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            subprocess.run(["screencapture", "-i", "-x", tmp.name], check=False)
        except Exception:
            return
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
            # เปิด editor โชว์ preview ก่อน -> user กด Paste เองตอนพร้อม
            try:
                _exec.spawn(["cropper", tmp.name])
            except Exception:
                pass
        else:
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    # ---- radial wheel ----
    def _open_wheel(self, icon=None, item=None) -> None:
        now = time.monotonic()
        if now - self._wheel_last < 1.0:
            return
        if self._wheel_proc is not None and self._wheel_proc.poll() is None:
            return  # วงล้อเปิดอยู่แล้ว
        self._wheel_last = now
        try:
            self._wheel_proc = _exec.spawn(["wheel"])
        except Exception:
            self._wheel_proc = None

    def _toggle_shake(self, icon=None, item=None) -> None:
        self.cfg.shake_trigger = not self.cfg.shake_trigger
        cfg_mod.save(self.cfg)
        if self.cfg.shake_trigger:
            self.shake.start()
        else:
            self.shake.stop()
        if self.cfg.sound:
            sound.play("toggle")

    def _quit(self, icon, item) -> None:
        self.shake.stop()
        icon.stop()

    # ---- menu ----
    def _build_menu(self) -> Menu:
        return Menu(
            # ---- Actions ----
            Item("Capture region…", self._capture_screen),
            Item("Open image wheel  (Ctrl+Alt+Space)", self._open_wheel,
                 default=True),
            Menu.SEPARATOR,
            # ---- Settings ----
            Item("Mouse-shake trigger", self._toggle_shake,
                 checked=lambda i: self.cfg.shake_trigger,
                 enabled=shake_available()),
            Item("Sound", self._toggle_sound, checked=lambda i: self.cfg.sound),
            Menu.SEPARATOR,
            Item("Quit", self._quit),
        )

    # ---- run ----
    def run(self) -> None:
        if self.cfg.shake_trigger:
            self.shake.start()
        hotkeys.start({
            self.cfg.hotkey_wheel: self._open_wheel,
        })
        self.icon.run()  # ต้องรันบน main thread (โดยเฉพาะ macOS)


def main() -> None:
    TrayApp().run()
