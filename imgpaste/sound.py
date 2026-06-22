"""เสียง feedback minimal — แยกโทน image vs path. ไม่พึ่ง dep เพิ่ม.

macOS: afplay system sound (.aiff)
Windows: winsound (stdlib)
เล่นแบบ non-blocking; เงียบเสมอถ้า play ไม่สำเร็จ.
"""

from __future__ import annotations

import subprocess
import sys

# event -> ชื่อ macOS system sound (/System/Library/Sounds/<name>.aiff)
_MAC_SOUNDS = {
    "image": "Pop",
    "path": "Tink",
    "toggle": "Morse",
    "hover": "Tink",
    "error": "Funk",
}


def play(event: str = "image") -> None:
    """เล่นเสียงตาม event. เงียบถ้าเล่นไม่ได้."""
    try:
        if sys.platform == "darwin":
            _play_macos(event)
        elif sys.platform == "win32":
            _play_windows(event)
    except Exception:
        pass


def _play_macos(event: str) -> None:
    name = _MAC_SOUNDS.get(event, "Pop")
    path = f"/System/Library/Sounds/{name}.aiff"
    # Popen = non-blocking; ไม่ต้องรอเสียงจบ
    subprocess.Popen(
        ["afplay", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _play_windows(event: str) -> None:
    import winsound

    beeps = {
        "image": winsound.MB_OK,
        "path": winsound.MB_ICONASTERISK,
        "toggle": winsound.MB_ICONQUESTION,
        "hover": winsound.MB_ICONASTERISK,
        "error": winsound.MB_ICONHAND,
    }
    winsound.MessageBeep(beeps.get(event, winsound.MB_OK))
