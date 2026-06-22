"""จำลอง keystroke paste (Cmd+V / Ctrl+V) ผ่าน pynput.

macOS: synthetic key ต้องมี Accessibility permission (อันเดียวกับ hotkey).
"""

from __future__ import annotations

import sys
import time

try:
    from pynput.keyboard import Controller, Key, KeyCode

    _HAS_PYNPUT = True
except Exception:
    _HAS_PYNPUT = False

# macOS virtual keycode ของปุ่ม V. ต้องใช้ vk (ไม่ใช่ char 'v') เพราะ pynput
# บน macOS ไม่ติด Command flag ให้ keydown ของ char -> Cmd+V ไม่ทำงาน.
_MAC_VK_V = 9


def available() -> bool:
    return _HAS_PYNPUT


def paste_detached(delay: float = 0.0) -> bool:
    """paste จาก subprocess สะอาด (fresh python) — เลี่ยง bug pynput macOS ที่
    synthetic key ถูกส่งซ้ำเมื่อมี Listener + NSApp.run() อยู่ใน process เดียวกัน
    (wheel/cropper). คืน True ถ้า spawn ได้.
    """
    import subprocess
    code = (
        "import time;time.sleep(%r);"
        "from imgpaste import paste;paste.paste()" % float(delay)
    )
    try:
        subprocess.Popen([sys.executable, "-c", code])
        return True
    except Exception:
        return False


def paste() -> None:
    """กด modifier+V วาง clipboard เข้า field ที่ focus อยู่. no-op ถ้าไม่มี pynput."""
    if not _HAS_PYNPUT:
        return
    if sys.platform == "darwin":
        mod, key = Key.cmd, KeyCode.from_vk(_MAC_VK_V)
    else:
        mod, key = Key.ctrl, KeyCode.from_char("v")
    kb = Controller()
    try:
        kb.press(mod)
        time.sleep(0.03)
        kb.press(key)
        time.sleep(0.03)
        kb.release(key)
        time.sleep(0.03)
        kb.release(mod)
    except Exception:
        pass
