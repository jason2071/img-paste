"""Visual quick-pick — grid thumbnail ของรูปล่าสุด.

รันเป็น process แยก (python -m imgpaste.picker) เพื่อเลี่ยงชน runloop ของ tray
บน macOS. คลิกซ้าย = copy image, คลิกขวา = copy path. เลือกแล้วปิดหน้าต่าง.
"""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from . import config as cfg_mod
from . import sound
from .clipboard import copy_image, copy_path

_COLS = 4
_THUMB = 128
_PAD = 8
_TRIM = 18


def _thumb(path: str) -> ImageTk.PhotoImage | None:
    try:
        im = Image.open(path)
        im.thumbnail((_THUMB, _THUMB))
        return ImageTk.PhotoImage(im)
    except Exception:
        return None


def run() -> None:
    cfg = cfg_mod.load()
    images = cfg_mod.recent_images(cfg)

    root = tk.Tk()
    root.title("ImgPaste — pick image")
    root.configure(bg="#16191f")
    root.attributes("-topmost", True)

    if not images:
        tk.Label(
            root, text="(no images found)", fg="#9aa4b2", bg="#16191f",
            padx=24, pady=24, font=("Helvetica", 13),
        ).pack()
        root.after(1500, root.destroy)
        root.mainloop()
        return

    refs: list[ImageTk.PhotoImage] = []  # กัน GC

    def choose(path: str, as_path: bool):
        if as_path:
            copy_path(path)
            if cfg.sound:
                sound.play("path")
        else:
            copy_image(path)
            if cfg.sound:
                sound.play("image")
        root.destroy()

    header = tk.Label(
        root, text="คลิก = copy image  ·  คลิกขวา = copy path",
        fg="#6f7b8a", bg="#16191f", pady=8, font=("Helvetica", 11),
    )
    header.grid(row=0, column=0, columnspan=_COLS, sticky="we")

    for idx, path in enumerate(images):
        photo = _thumb(path)
        if photo is None:
            continue
        refs.append(photo)
        r, c = divmod(idx, _COLS)
        cell = tk.Frame(root, bg="#1f242c", padx=_PAD, pady=_PAD)
        cell.grid(row=r + 1, column=c, padx=_PAD, pady=_PAD)

        name = path.rsplit("/", 1)[-1]
        label = name if len(name) <= _TRIM else name[: _TRIM - 1] + "…"

        btn = tk.Label(cell, image=photo, bg="#1f242c", cursor="hand2")
        btn.pack()
        cap = tk.Label(cell, text=label, fg="#c3ccd8", bg="#1f242c",
                       font=("Helvetica", 10))
        cap.pack(pady=(4, 0))

        for w in (btn, cap):
            w.bind("<Button-1>", lambda e, p=path: choose(p, False))
            w.bind("<Button-2>", lambda e, p=path: choose(p, True))
            w.bind("<Button-3>", lambda e, p=path: choose(p, True))

    root.bind("<Escape>", lambda e: root.destroy())
    root.mainloop()


if __name__ == "__main__":
    run()
