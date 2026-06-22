"""Watch โฟลเดอร์หารูปใหม่.

ใช้ watchdog (event-driven) ถ้ามี ไม่งั้น fallback เป็น polling.
callback on_new(path) ถูกเรียกจาก background thread เมื่อรูปใหม่ "เขียนเสร็จ" แล้ว.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable

from . import config as cfg_mod
from .config import Config

OnNew = Callable[[str], None]

# รอไฟล์เขียนเสร็จ (screenshot create-then-rename / download .part)
_SETTLE_POLL = 0.15
_SETTLE_TIMEOUT = 5.0


def _wait_until_stable(path: str) -> bool:
    """รอจน size นิ่ง + เปิดอ่านได้. คืน False ถ้าไฟล์หาย/ timeout."""
    deadline = time.monotonic() + _SETTLE_TIMEOUT
    last = -1
    while time.monotonic() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size > 0 and size == last:
            return True
        last = size
        time.sleep(_SETTLE_POLL)
    return os.path.exists(path)


class _Dedup:
    """กันยิง callback ซ้ำสำหรับ path เดิมในช่วงสั้น ๆ."""

    def __init__(self, window: float = 2.0):
        self._window = window
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def fresh(self, path: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._seen = {p: t for p, t in self._seen.items() if now - t < self._window}
            if path in self._seen:
                return False
            self._seen[path] = now
            return True


class Watcher:
    def __init__(self, cfg: Config, on_new: OnNew):
        self._cfg = cfg
        self._on_new = on_new
        self._dedup = _Dedup()
        self._running = True
        self._observer = None
        self._poll_thread: threading.Thread | None = None
        self.mode = "none"  # "watchdog" | "polling"

    # ---- public ----
    def start(self) -> "Watcher":
        if not self._start_watchdog():
            self._start_polling()
        return self

    def stop(self) -> None:
        self._running = False
        if self._observer is not None:
            try:
                self._observer.stop()
            except Exception:
                pass

    # ---- internal: dispatch a candidate path ----
    def _handle(self, path: str) -> None:
        if not self._running or not self._cfg.is_image(os.path.basename(path)):
            return
        if not self._dedup.fresh(path):
            return

        def worker():
            if _wait_until_stable(path) and self._running:
                try:
                    self._on_new(path)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    # ---- watchdog backend ----
    def _start_watchdog(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            return False

        handler_self = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    handler_self._handle(event.src_path)

            def on_moved(self, event):
                if not event.is_directory:
                    handler_self._handle(event.dest_path)

        observer = Observer()
        watched = 0
        handler = _Handler()
        for d in self._cfg.dirs:
            if os.path.isdir(d):
                observer.schedule(handler, d, recursive=False)
                watched += 1
        if watched == 0:
            return False
        observer.daemon = True
        observer.start()
        self._observer = observer
        self.mode = "watchdog"
        return True

    # ---- polling fallback ----
    def _start_polling(self) -> None:
        self.mode = "polling"
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        seen = set(cfg_mod.recent_images(self._cfg, limit=200))
        while self._running:
            time.sleep(self._cfg.refresh_sec)
            current = cfg_mod.recent_images(self._cfg, limit=200)
            for p in current:
                if p not in seen:
                    self._handle(p)
            seen = set(current)
