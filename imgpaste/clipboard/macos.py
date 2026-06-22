"""macOS clipboard backend — NSPasteboard (เร็ว) + osascript fallback."""

from __future__ import annotations

import subprocess
import tempfile

from PIL import Image

# optional: รองรับ .heic screenshot
try:
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
except Exception:
    pass

try:
    from AppKit import NSImage, NSPasteboard, NSPasteboardTypePNG

    _HAS_APPKIT = True
except Exception:
    _HAS_APPKIT = False


def _copy_image_osascript(path: str) -> None:
    """Fallback: แปลงเป็น PNG ชั่วคราวแล้วสั่ง clipboard ผ่าน osascript."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    Image.open(path).convert("RGBA").save(tmp.name, "PNG")
    script = (
        "set the clipboard to "
        f'(read (POSIX file "{tmp.name}") as «class PNGf»)'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def copy_image(path: str) -> None:
    if _HAS_APPKIT:
        # ลง pasteboard เป็น PNG "type เดียว" — เลี่ยง NSImage ที่ลงหลาย
        # representation (TIFF+PDF) ทำบาง app วาง 2 ภาพ
        try:
            from io import BytesIO

            from Foundation import NSData
            buf = BytesIO()
            Image.open(path).convert("RGBA").save(buf, "PNG")
            raw = buf.getvalue()
            png = NSData.dataWithBytes_length_(raw, len(raw))
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.declareTypes_owner_([NSPasteboardTypePNG], None)
            if pb.setData_forType_(png, NSPasteboardTypePNG):
                return
        except Exception:
            pass
    _copy_image_osascript(path)


def copy_path(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
