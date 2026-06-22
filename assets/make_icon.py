"""สร้าง app icon (.png 1024 / .ico / .icns) จาก glyph เดียวกับ tray (icon.py)
แต่เป็นเวอร์ชันสี เต็มใบ บนพื้น rounded-square gradient.

รัน: python assets/make_icon.py   (macOS ต้องมี iconutil สำหรับ .icns)
output: assets/imgpaste.png, assets/imgpaste.ico, assets/imgpaste.icns
"""

from __future__ import annotations

import os
import shutil
import subprocess

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
_TOP = (96, 105, 245)       # indigo
_BOT = (162, 92, 246)       # violet
_FG = (255, 255, 255, 255)


def _bg() -> Image.Image:
    """rounded-square + แนวทแยง gradient indigo->violet."""
    grad = Image.new("RGB", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(_TOP, _BOT))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    m = S // 16                                  # margin -> full-bleed นิด
    ImageDraw.Draw(mask).rounded_rectangle(
        [m, m, S - m, S - m], radius=int(S * 0.225), fill=255)
    out.paste(grad, (0, 0), mask)
    return out


def build() -> Image.Image:
    img = _bg()
    d = ImageDraw.Draw(img)
    # photo frame (outline) — สเกลจาก icon.py [9,13,55,51]/64 -> 1024
    d.rounded_rectangle([232, 300, 792, 724], radius=72, outline=_FG, width=40)
    # ดวงอาทิตย์ มุมซ้ายบนในกรอบ
    d.ellipse([312, 372, 432, 492], fill=_FG)
    # ภูเขา ฐานแตะขอบล่างในกรอบ
    d.polygon(
        [(296, 700), (456, 470), (540, 560), (664, 420), (760, 700)],
        fill=_FG,
    )
    return img


def main() -> None:
    img = build()
    png = os.path.join(HERE, "imgpaste.png")
    img.save(png)
    # .ico (multi-size) — Windows
    img.save(os.path.join(HERE, "imgpaste.ico"),
             sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    # .icns (macOS) ผ่าน iconutil
    if shutil.which("iconutil"):
        iconset = os.path.join(HERE, "imgpaste.iconset")
        os.makedirs(iconset, exist_ok=True)
        spec = [(16, ""), (16, "@2x"), (32, ""), (32, "@2x"),
                (128, ""), (128, "@2x"), (256, ""), (256, "@2x"),
                (512, ""), (512, "@2x")]
        for base, suf in spec:
            px = base * (2 if suf else 1)
            img.resize((px, px), Image.LANCZOS).save(
                os.path.join(iconset, f"icon_{base}x{base}{suf}.png"))
        subprocess.run(
            ["iconutil", "-c", "icns", iconset,
             "-o", os.path.join(HERE, "imgpaste.icns")], check=True)
        shutil.rmtree(iconset)
        print("wrote imgpaste.png / .ico / .icns")
    else:
        print("wrote imgpaste.png / .ico (no iconutil -> ข้าม .icns)")


if __name__ == "__main__":
    main()
