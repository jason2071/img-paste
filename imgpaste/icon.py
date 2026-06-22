"""Tray icon — flat minimal + state/flash variants.

make_icon(auto=False, flash=False):
  auto  -> จุด accent เขียว (auto-copy เปิด) / เทา (ปิด)
  flash -> สว่างขึ้นชั่วขณะ (micro-animation ตอน copy)
"""

from __future__ import annotations

from PIL import Image, ImageDraw

_BODY = (34, 40, 49, 255)
_BODY_FLASH = (70, 84, 102, 255)
_ACCENT = (120, 200, 170, 255)
_SUN = (240, 200, 90, 255)
_ON = (110, 220, 140, 255)
_OFF = (110, 120, 130, 255)


def make_icon(auto: bool = False, flash: bool = False) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    body = _BODY_FLASH if flash else _BODY
    d.rounded_rectangle([8, 8, 56, 58], radius=8, fill=body)
    d.rounded_rectangle([24, 3, 40, 13], radius=4, fill=_ACCENT)          # clip
    d.ellipse([18, 20, 28, 30], fill=_SUN)                                # sun
    d.polygon([(14, 50), (28, 34), (37, 44), (46, 30), (52, 50)],
              fill=_ACCENT)                                               # mountains

    # state dot มุมขวาล่าง — เขียว=auto on, เทา=off
    dot = _ON if auto else _OFF
    d.ellipse([46, 46, 58, 58], fill=dot, outline=(20, 24, 30, 255), width=2)
    return img
