"""Tray icon — monochrome line-art glyph, macOS template-friendly.

บน macOS menu bar icon ถูก render เป็น *template image*: pixel ทึบทุกจุดจะถูก
tint เป็นสีเดียว (ขาวบน dark menu bar / ดำบน light) ตามธีมระบบ — เหมือน icon
เพื่อน ๆ ตัวอื่น. ดังนั้น detail ต้องมาจาก "ช่องว่าง" (alpha) ไม่ใช่จากสี.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

# foreground — บน macOS ถูก tint ทับด้วยสีระบบอยู่แล้ว (ค่าสีจึงไม่สำคัญ);
# platform อื่นที่โชว์สีจริงจะเห็นโทนนี้
_FG = (228, 230, 235, 255)


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # กรอบรูป (outline เท่านั้น -> ข้างในโปร่ง อ่านออกตอน tint)
    d.rounded_rectangle([9, 13, 55, 51], radius=8, outline=_FG, width=5)

    # ดวงอาทิตย์ มุมซ้ายบนในกรอบ
    d.ellipse([17, 19, 27, 29], fill=_FG)

    # ภูเขา — ฐานแตะขอบล่างในกรอบ
    d.polygon(
        [(13, 47), (26, 31), (33, 39), (43, 27), (51, 47)],
        fill=_FG,
    )
    return img
