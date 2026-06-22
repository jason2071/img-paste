# imgpaste

Menu bar / system tray helper (macOS + Windows). ถ่าย screenshot หรือโหลดรูป →
**copy เข้า clipboard อัตโนมัติ** → `Cmd/Ctrl+V` วางเข้าช่องแชท (Claude Desktop/CLI,
Codex, browser agents) หรือ copy path เข้า CLI ได้ทันที.

## ทำไม / อะไรใหม่

- **Auto-copy mode** — รูปใหม่ลงโฟลเดอร์ที่ watch → copy เป็น image เข้า clipboard
  ทันที. ถ่าย screenshot แล้วกด `Cmd+V` ได้เลย ไม่ต้องเปิดเมนู
- **Event-driven watch** (`watchdog`) — เร็ว, จับ pattern create-then-rename ของ
  macOS screenshot ได้; fallback เป็น polling ถ้าไม่มี watchdog
- **Radial image wheel** — focus ช่อง input → **สะบัดเมาส์แรง ๆ** (หรือ
  `Ctrl+Alt+Space`) → วงล้อ 3×3 เด้งกลางจอ (โปร่งใส, AppKit): กลาง = สลับ
  Desktop/Downloads, รอบ ๆ = การ์ดรูปล่าสุด → hover zoom → คลิกเลือก → copy + paste
- **Capture region + annotate** — เมนู Capture region… → ลากเลือกพื้นที่จอ
  (เหมือน Cmd+Shift+4) → preview editor สไตล์ CleanShot: crop / วาด (rect/oval/line)
  / ใส่สี → Send (copy + auto paste)
- **เสียง feedback minimal** — แยกโทน image / path / hover, ปิดได้
- **Config file** — `~/.config/imgpaste/config.toml` (สร้าง default ให้ครั้งแรก)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                 # หรือ: pip install -r requirements.txt
# HEIC screenshot (optional): pip install -e ".[heic]"
```

> `pynput` เป็นออปชัน — ไม่มีก็ได้ แต่ global hotkey จะปิด (เมนูยังใช้ได้)

## Run

```bash
imgpaste            # หรือ: python -m imgpaste
```

## ใช้งาน

- คลิกไอคอน menu bar / tray → เมนู
  - **Copy newest image / path** — copy รูปล่าสุดทันที
  - **Auto-copy new images** ✓ — เปิด/ปิดโหมดอัตโนมัติ (จุดไอคอนเขียว = เปิด)
  - **Sound** ✓ — เปิด/ปิดเสียง
  - **Open image wheel** — เปิดวงล้อ (เหมือนสะบัดเมาส์)
  - **Mouse-shake trigger** ✓ — เปิด/ปิดการสะบัดเมาส์เรียกวงล้อ
  - **Capture region…** — ลากเลือกพื้นที่จอ → เปิด preview/annotate editor
- **Hotkey:** `Ctrl+Alt+V` = copy newest image · `Ctrl+Alt+B` = copy newest path ·
  `Ctrl+Alt+Space` = เปิดวงล้อ

### วงล้อ (radial wheel)

focus ช่อง input → สะบัดเมาส์แรง ๆ (ซ้าย-ขวาเร็ว ๆ) หรือกด `Ctrl+Alt+Space`:

- **พื้นหลังโปร่งใสจริง** (macOS AppKit NSWindow) — เห็นแค่การ์ดลอย ไม่มีกล่องสี่เหลี่ยม
- **grid 3×3**: hub อยู่ช่องกลาง (source toggle), รอบ ๆ 8 การ์ดรูปล่าสุด
- ชี้เมาส์ไปทางการ์ด → **zoom ใหญ่ขึ้น** + ขอบ accent → **คลิกซ้าย** = เลือก
- มีเสียง tick ตอน hover เปลี่ยนการ์ด
- **ธีมสี** สลับได้ที่ `wheel_theme`: `aurora` (default, มิ้นต์), `ember` (gold),
  `void_mono` (ขาวล้วน), `lavender_glass` (ม่วง), `floating_orbs` (ฟ้า)
- `Esc` / คลิกขวา = ยกเลิก
- เลือกแล้ว → copy + paste เข้า input ที่ focus ไว้ให้อัตโนมัติ

> paste / hotkey / สะบัดเมาส์ ต้องอนุญาต **Accessibility** ให้ Terminal/Python
> (macOS). บน macOS ใช้ virtual keycode สำหรับ `Cmd+V` (char `v` ติด bug pynput).

### Capture region + annotate

เมนู **Capture region…** → ลากเลือกพื้นที่จอ (เหมือน Cmd+Shift+4) → เปิด preview
editor (สไตล์ CleanShot): toolbar ลอยใต้ภาพ (vector icons, rounded) + flyout
เลือก stroke/สี

- **Tools** — crop, rectangle, oval, line · undo/redo
- **Flyout** — ขนาดเส้น (S/M/L) + สวอตช์สี + color picker
- **Save** เซฟ PNG · **✓ Send** = copy รูป (crop+วาด) + auto `Cmd+V` เข้า app
  ที่ focus ไว้ก่อนหน้า แล้วปิด editor · **Esc** ปิด
- ลากไฟล์รูปมาวางใน editor ก็ได้ (`tkinterdnd2`) หรือ Open ผ่าน dialog

### macOS permissions

Global hotkey ต้องอนุญาต Accessibility ให้ Terminal/Python:
**System Settings → Privacy & Security → Accessibility**

## Config

`~/.config/imgpaste/config.toml`:

```toml
watch_dirs   = ["~/Desktop", "~/Downloads"]
image_exts   = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"]
auto_copy    = false
sound        = true
animations   = true
hotkey_image = "<ctrl>+<alt>+v"
hotkey_path  = "<ctrl>+<alt>+b"
# radial wheel + paste
auto_paste        = true
paste_delay       = 0.3
shake_trigger     = true
shake_sensitivity = 4               # จำนวนการกลับทิศก่อนเด้งวงล้อ (มาก=ต้องสะบัดแรงขึ้น)
wheel_slots       = 8                # จำนวนช่องในวงล้อ
wheel_theme       = "aurora"         # aurora|ember|void_mono|lavender_glass|floating_orbs
hotkey_wheel      = "<ctrl>+<alt>+<space>"
```

## โครงสร้าง

```
imgpaste/
  app.py        # TrayApp orchestration
  config.py     # TOML config + recent_images
  watcher.py    # watchdog watch + polling fallback
  clipboard/    # macos.py / windows.py backends
  wheel.py      # radial 3×3 image wheel — AppKit, themeable (process แยก)
  cropper.py    # capture/crop/annotate editor — Tk CleanShot-style (process แยก)
  shake.py      # mouse-shake detector (pynput)
  paste.py      # synthetic Cmd/Ctrl+V (pynput)
  picker.py     # Tk thumbnail grid (wheel fallback บน non-macOS)
  sound.py      # afplay / winsound feedback
  hotkeys.py    # pynput global hotkeys (optional)
  icon.py       # tray icon state + flash
```
