# imgpaste

Menu bar / system tray helper (macOS + Windows). ถ่าย screenshot หรือโหลดรูป →
**copy เข้า clipboard อัตโนมัติ** → `Cmd/Ctrl+V` วางเข้าช่องแชท (Claude Desktop/CLI,
Codex, browser agents) หรือ copy path เข้า CLI ได้ทันที.

## ทำไม / อะไรใหม่

- **Auto-copy mode** — รูปใหม่ลงโฟลเดอร์ที่ watch → copy เป็น image เข้า clipboard
  ทันที. ถ่าย screenshot แล้วกด `Cmd+V` ได้เลย ไม่ต้องเปิดเมนู
- **Event-driven watch** (`watchdog`) — เร็ว, จับ pattern create-then-rename ของ
  macOS screenshot ได้; fallback เป็น polling ถ้าไม่มี watchdog
- **Visual quick-pick** — เมนู "Pick image…" เปิด grid thumbnail เลือกด้วยตา
- **เสียง feedback minimal** — แยกโทน image / path, ปิดได้
- **Config file** — `~/.config/imgpaste/config.toml` (สร้าง default ให้ครั้งแรก)
- **Radial image wheel (GTA-style)** — focus ช่อง input → **สะบัดเมาส์แรง ๆ**
  (หรือ `Ctrl+Alt+Space`) → วงล้อเด้งกลางจอ: กลาง = สลับ Desktop/Downloads,
  รอบนอก = 8 ภาพล่าสุด → ชี้ทิศ + คลิกเลือก → copy + paste เข้า input ให้เลย

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
  - **Capture region → paste** — ลากเลือกพื้นที่จอเอง (เหมือน Cmd+Shift+4) →
    copy เข้า clipboard + auto `Cmd+V` วางเข้า app ที่ focus ไว้
  - **Crop & annotate…** — เปิด editor: ลากรูปเข้า → crop → วาด/ใส่สี → paste
  - **Pick image…** — เปิด grid thumbnail (คลิก=image, คลิกขวา=path)
- **Hotkey:** `Ctrl+Alt+V` = copy newest image · `Ctrl+Alt+B` = copy newest path ·
  `Ctrl+Alt+Space` = เปิดวงล้อ

### วงล้อ (radial wheel)

focus ช่อง input → สะบัดเมาส์แรง ๆ (ซ้าย-ขวาเร็ว ๆ) หรือกด `Ctrl+Alt+Space`:

- วงล้อ donut กลม **พื้นหลังโปร่งใสจริง** (macOS AppKit NSWindow) — เห็นแค่วงลอย
  ไม่มีกล่องสี่เหลี่ยม
- แบ่ง **8 ช่อง (wedge) มี gap คั่นชัด** แต่ละช่องใส่ **thumbnail**
- **กลางวง** — source (Desktop/Downloads), คลิกเพื่อสลับ
- ชี้เมาส์ไปทางช่อง → ช่องสว่าง + ภาพโต → **คลิกซ้าย** = เลือก
- **ธีมสี** สลับได้ที่ `wheel_theme`: `aurora` (default, มิ้นต์), `ember` (gold),
  `void_mono` (ขาวล้วน), `lavender_glass` (ม่วง), `floating_orbs` (ฟ้า)
- `Esc` / คลิกขวา = ยกเลิก
- เลือกแล้ว → copy + paste เข้า input ที่ focus ไว้ให้อัตโนมัติ

> paste / hotkey / สะบัดเมาส์ ต้องอนุญาต **Accessibility** ให้ Terminal/Python
> (macOS). บน macOS ใช้ virtual keycode สำหรับ `Cmd+V` (char `v` ติด bug pynput).

### Crop & annotate

เมนู **Crop & annotate…** → หน้าต่าง editor:

1. **ลากรูปไฟล์มาวาง** (drag-drop, ใช้ `tkinterdnd2`) หรือกด **Open…**
2. **Crop** — ลากกรอบเลือกพื้นที่ → ปุ่ม **✂ Crop** (หรือ **✎ Annotate ▶** ข้าม crop)
3. **วาด** — เลือกเครื่องมือ **▭ / ◯ / ╱** + สี (swatches หรือ 🎨 custom) → ลากบนรูป
   · **↶ Undo** ลบชิ้นล่าสุด
4. **💾 Save** เซฟ PNG · **📋 Paste** = copy รูป (crop+วาด) + auto `Cmd+V` เข้า app
   ที่ focus ไว้ก่อนหน้า แล้วปิด editor

> ไม่มี `tkinterdnd2` ก็ใช้ได้ — drag-drop ปิด แต่ปุ่ม Open… ยังเลือกไฟล์ได้

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
  picker.py     # Tk thumbnail quick-pick (process แยก)
  wheel.py      # radial GTA-style image wheel (process แยก)
  shake.py      # mouse-shake detector (pynput)
  paste.py      # synthetic Cmd/Ctrl+V (pynput)
  sound.py      # afplay / winsound feedback
  hotkeys.py    # pynput global hotkeys (optional)
  icon.py       # tray icon state + flash
```
