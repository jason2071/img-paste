"""Spawn child processes that work both in dev and in a frozen PyInstaller app.

Dev:    python -m imgpaste <subcommand> [args...]
Frozen: <app-binary> <subcommand> [args...]   (sys.executable คือตัว app เอง,
        ไม่รับ `-m`/`-c` — ต้อง re-exec ผ่าน subcommand router ใน __main__.py)
"""

from __future__ import annotations

import subprocess
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def spawn(args: list[str], **kw) -> subprocess.Popen:
    """Launch self with a subcommand. `args` = ['wheel'] / ['cropper', path] / ['paste']."""
    if is_frozen():
        cmd = [sys.executable, *args]
    else:
        cmd = [sys.executable, "-m", "imgpaste", *args]
    return subprocess.Popen(cmd, **kw)
