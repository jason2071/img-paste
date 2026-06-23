"""ตรวจจับ "สะบัดเมาส์" เพื่อเปิดวงล้อ.

นับการกลับทิศ (reversal) ของแกน X ภายในกรอบเวลาสั้น ๆ. pynput.mouse global
listener — macOS ต้อง Accessibility permission. ไม่มี pynput -> no-op.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

try:
    from pynput import mouse as _pm

    _HAS_PYNPUT = True
except Exception:
    _HAS_PYNPUT = False

# จิ๊กเล็ก ๆ ที่ถือว่าเป็น noise ไม่นับเป็นการเคลื่อน
_MIN_STEP = 6
# ระยะรวมขั้นต่ำ (กันสั่นนิดเดียวแล้วเด้ง)
_MIN_TRAVEL = 180


def available() -> bool:
    return _HAS_PYNPUT


def count_reversals(xs: list[float], min_step: float = _MIN_STEP) -> int:
    """นับจำนวนครั้งที่ทิศการเคลื่อน X กลับด้าน (pure, test ได้)."""
    reversals = 0
    last_sign = 0
    for dx in (b - a for a, b in zip(xs, xs[1:])):
        if abs(dx) < min_step:
            continue
        sign = 1 if dx > 0 else -1
        if last_sign and sign != last_sign:
            reversals += 1
        last_sign = sign
    return reversals


class ShakeDetector:
    def __init__(
        self,
        on_shake: Callable[[], None],
        sensitivity: int = 3,
        window: float = 0.5,
        cooldown: float = 1.5,
    ):
        self._on_shake = on_shake
        self._sensitivity = sensitivity
        self._window = window
        self._cooldown = cooldown
        self._samples: deque[tuple[float, float, float]] = deque()
        self._last_fire = 0.0
        self._listener = None
        self._lock = threading.Lock()

    def start(self) -> "ShakeDetector":
        if not _HAS_PYNPUT or self._listener is not None:
            return self
        try:
            self._listener = _pm.Listener(on_move=self._on_move)
            self._listener.start()
        except Exception:
            self._listener = None
        return self

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _on_move(self, x, y) -> None:
        now = time.monotonic()
        with self._lock:
            self._samples.append((now, x, y))
            cutoff = now - self._window
            while self._samples and self._samples[0][0] < cutoff:
                self._samples.popleft()
            if now - self._last_fire < self._cooldown:
                return
            if len(self._samples) < self._sensitivity + 1:
                return
            xs = [px for _, px, _ in self._samples]
            ys = [py for _, _, py in self._samples]
            # ระยะจริง (euclidean path) — รองรับสะบัดแนวตั้ง/เฉียง ไม่ใช่แค่ X
            travel = sum(((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                         for (ax, ay), (bx, by) in zip(zip(xs, ys), zip(xs[1:], ys[1:])))
            if travel < _MIN_TRAVEL:
                return
            # นับ reversal ทั้งสองแกน เอาแกนที่สะบัดเด่นสุด
            reversals = max(count_reversals(xs), count_reversals(ys))
            if reversals >= self._sensitivity:
                self._last_fire = now
                self._samples.clear()
                fire = True
            else:
                fire = False
        if fire:
            try:
                self._on_shake()
            except Exception:
                pass
