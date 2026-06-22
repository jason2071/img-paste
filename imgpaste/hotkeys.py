"""Global hotkeys ผ่าน pynput (optional).

start(mapping) -> listener หรือ None ถ้า pynput ไม่มี.
macOS ต้องอนุญาต Accessibility ให้ Terminal/Python.
"""

from __future__ import annotations

from typing import Callable

try:
    from pynput import keyboard as _pk

    HAS_HOTKEYS = True
except Exception:
    HAS_HOTKEYS = False


def start(mapping: dict[str, Callable[[], None]]):
    """รับ {"<ctrl>+<alt>+v": fn, ...}. คืน listener (มี .stop()) หรือ None."""
    if not HAS_HOTKEYS:
        return None
    try:
        listener = _pk.GlobalHotKeys(mapping)
        listener.start()
        return listener
    except Exception:
        return None
