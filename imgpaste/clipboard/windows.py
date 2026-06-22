"""Windows clipboard backend — win32clipboard (CF_DIB / CF_UNICODETEXT)."""

from __future__ import annotations

import io

from PIL import Image

import win32clipboard
import win32con


def copy_image(path: str) -> None:
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    data = buf.getvalue()[14:]  # CF_DIB = BMP ตัด file header 14 ไบต์
    buf.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


def copy_path(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
