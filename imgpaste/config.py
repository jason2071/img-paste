"""Config + recent-image helpers.

Config อยู่ที่ ~/.config/imgpaste/config.toml (เขียน default ให้ครั้งแรก).
แก้ไฟล์นั้นแทนการแก้ source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

DEFAULT_WATCH_DIRS = ["~/Desktop", "~/Downloads"]
DEFAULT_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"]

CONFIG_DIR = Path(os.path.expanduser("~")) / ".config" / "imgpaste"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass
class Config:
    watch_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_WATCH_DIRS))
    image_exts: list[str] = field(default_factory=lambda: list(DEFAULT_IMAGE_EXTS))
    max_items: int = 12
    sound: bool = True
    # radial wheel + paste
    auto_paste: bool = True
    paste_delay: float = 0.2
    shake_trigger: bool = True
    shake_sensitivity: int = 4
    wheel_slots: int = 8
    wheel_theme: str = "aurora"
    hotkey_wheel: str = "<ctrl>+<alt>+<space>"

    # ---- derived ----
    @property
    def dirs(self) -> list[str]:
        return [os.path.expanduser(d) for d in self.watch_dirs]

    @property
    def exts(self) -> set[str]:
        return {e.lower() for e in self.image_exts}

    def is_image(self, name: str) -> bool:
        return os.path.splitext(name)[1].lower() in self.exts


def load() -> Config:
    """อ่าน config; ถ้าไม่มีไฟล์ -> สร้าง default แล้วคืนค่า default."""
    if tomllib is not None and CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                data = tomllib.load(f)
            return _from_dict(data)
        except Exception:
            pass  # config เสีย -> ใช้ default
    cfg = Config()
    try:
        save(cfg)
    except Exception:
        pass
    return cfg


def _from_dict(data: dict) -> Config:
    cfg = Config()
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def save(cfg: Config) -> None:
    """เขียน config เป็น TOML (เขียนเองไม่พึ่ง lib)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(_to_toml(asdict(cfg)), encoding="utf-8")


def _to_toml(d: dict) -> str:
    lines = ["# imgpaste config — แก้ค่าได้ตามต้องการ", ""]
    for k, v in d.items():
        lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines) + "\n"


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    raise TypeError(f"unsupported TOML value: {v!r}")


def recent_images(cfg: Config, limit: int | None = None) -> list[str]:
    """คืน path รูปเรียงใหม่->เก่า ตาม mtime ข้ามทุก watch dir."""
    limit = cfg.max_items if limit is None else limit
    files: list[tuple[float, str]] = []
    for d in cfg.dirs:
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if not cfg.is_image(name):
                continue
            p = os.path.join(d, name)
            try:
                files.append((os.path.getmtime(p), p))
            except OSError:
                pass
    files.sort(reverse=True)
    return [p for _, p in files[:limit]]
