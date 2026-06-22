"""Clipboard layer — dispatch by platform.

copy_image(path) : วางรูปลง clipboard เป็น image (paste ในแชท/browser)
copy_path(text)  : วาง path เป็น text (paste ใน CLI)
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    from .windows import copy_image, copy_path
elif sys.platform == "darwin":
    from .macos import copy_image, copy_path
else:  # pragma: no cover
    def copy_image(path: str) -> None:  # type: ignore[misc]
        raise SystemExit("รองรับเฉพาะ Windows และ macOS")

    def copy_path(text: str) -> None:  # type: ignore[misc]
        raise SystemExit("รองรับเฉพาะ Windows และ macOS")

__all__ = ["copy_image", "copy_path"]
