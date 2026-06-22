"""TrayApp — orchestrate menu + watcher + hotkeys + icon state.

ฟีเจอร์หลัก: Auto-copy mode (รูปใหม่ลง -> copy เข้า clipboard ทันที).
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
from .clipboard import copy_image, copy_path
from .shake import ShakeDetector
from .shake import available as shake_available
from .watcher import Watcher

_FLASH_MS = 150


class TrayApp:
    def __init__(self):
        self.cfg = cfg_mod.load()
        self.count = 0
        self._flash_timer: threading.Timer | None = None
        self.icon = pystray.Icon(
            "imgpaste",
            icon.make_icon(auto=self.cfg.auto_copy),
            self._title(),
            menu=self._build_menu(),
        )
        self.watcher = Watcher(self.cfg, self._on_new_image)
        self.shake = ShakeDetector(
            self._open_wheel, sensitivity=self.cfg.shake_sensitivity
        )
        self._wheel_proc: subprocess.Popen | None = None
        self._wheel_last = 0.0

    # ---- helpers ----
    def _title(self) -> str:
        return f"ImgPaste · {self.count} copied" if self.count else "ImgPaste"

    def _notify(self, msg: str) -> None:
        try:
            self.icon.notify(msg, "ImgPaste")
        except Exception:
            pass

    def _refresh_icon(self, flash: bool = False) -> None:
        try:
            self.icon.icon = icon.make_icon(auto=self.cfg.auto_copy, flash=flash)
            self.icon.title = self._title()
        except Exception:
            pass

    def _flash(self) -> None:
        if not self.cfg.animations:
            return
        self._refresh_icon(flash=True)
        if self._flash_timer is not None:
            self._flash_timer.cancel()
        self._flash_timer = threading.Timer(_FLASH_MS / 1000, self._refresh_icon)
        self._flash_timer.daemon = True
        self._flash_timer.start()

    def _feedback(self, kind: str, name: str) -> None:
        """รวม notify + sound + flash + counter หลัง copy สำเร็จ."""
        self.count += 1
        glyph = "image" if kind == "image" else "path"
        self._notify(f"✓ {glyph} · {name}")
        if self.cfg.sound:
            sound.play(kind)
        self._flash()

    # ---- copy actions ----
    def _copy_image(self, path: str) -> None:
        copy_image(path)
        self._feedback("image", os.path.basename(path))

    def _copy_path(self, path: str) -> None:
        copy_path(path)
        self._feedback("path", os.path.basename(path))

    def _copy_newest_image(self, icon=None, item=None) -> None:
        imgs = cfg_mod.recent_images(self.cfg, limit=1)
        if imgs:
            self._copy_image(imgs[0])

    def _copy_newest_path(self, icon=None, item=None) -> None:
        imgs = cfg_mod.recent_images(self.cfg, limit=1)
        if imgs:
            self._copy_path(imgs[0])

    # ---- auto-copy callback (จาก watcher thread) ----
    def _on_new_image(self, path: str) -> None:
        if self.cfg.auto_copy:
            self._copy_image(path)

    # ---- toggles ----
    def _toggle_auto(self, icon=None, item=None) -> None:
        self.cfg.auto_copy = not self.cfg.auto_copy
        cfg_mod.save(self.cfg)
        self._refresh_icon()
        if self.cfg.sound:
            sound.play("toggle")
        self._notify("Auto-copy: ON" if self.cfg.auto_copy else "Auto-copy: OFF")

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
                subprocess.Popen([sys.executable, "-m", "imgpaste.cropper", tmp.name])
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
            self._wheel_proc = subprocess.Popen(
                [sys.executable, "-m", "imgpaste.wheel"]
            )
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
        self.watcher.stop()
        self.shake.stop()
        icon.stop()

    # ---- menu ----
    def _build_menu(self) -> Menu:
        return Menu(
            Item("Copy newest image  (Ctrl+Alt+V)",
                 self._copy_newest_image, default=True),
            Item("Copy newest path  (Ctrl+Alt+B)", self._copy_newest_path),
            Menu.SEPARATOR,
            Item("Auto-copy new images", self._toggle_auto,
                 checked=lambda i: self.cfg.auto_copy),
            Item("Sound", self._toggle_sound, checked=lambda i: self.cfg.sound),
            Menu.SEPARATOR,
            Item("Open image wheel  (Ctrl+Alt+Space)", self._open_wheel),
            Item("Mouse-shake trigger", self._toggle_shake,
                 checked=lambda i: self.cfg.shake_trigger,
                 enabled=shake_available()),
            Item("Capture region…", self._capture_screen),
            Menu.SEPARATOR,
            Item("Quit", self._quit),
        )

    # ---- run ----
    def run(self) -> None:
        self.watcher.start()
        if self.cfg.shake_trigger:
            self.shake.start()
        hotkeys.start({
            self.cfg.hotkey_image: self._copy_newest_image,
            self.cfg.hotkey_path: self._copy_newest_path,
            self.cfg.hotkey_wheel: self._open_wheel,
        })
        self.icon.run()  # ต้องรันบน main thread (โดยเฉพาะ macOS)


def main() -> None:
    TrayApp().run()
