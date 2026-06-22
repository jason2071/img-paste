# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`imgpaste` — macOS/Windows menu-bar (tray) helper that gets images into chat/CLI fast.
Watches Desktop/Downloads, auto-copies new screenshots to the clipboard, plus two
floating AppKit overlays: a radial **image wheel** (GTA weapon-wheel) and a
**capture/crop/annotate editor**. macOS is the primary target.

## Commands

```bash
# setup (Python 3.11+; venv already at ./.venv using python3.14)
./.venv/bin/python -m pip install -e .          # editable install
# or: pip install -r requirements.txt

./.venv/bin/python -m imgpaste                  # run tray app (== console script `imgpaste`)

# launch components standalone (each runs as its own process — see Architecture)
./.venv/bin/python -m imgpaste.wheel            # radial image wheel
./.venv/bin/python -m imgpaste.cropper <img>    # editor on an existing image
./.venv/bin/python -m imgpaste.cropper --capture  # screencapture -i then editor
./.venv/bin/python -m imgpaste.picker           # Tk grid fallback (non-mac)

IMGPASTE_AUTOPICK=0 ./.venv/bin/python -m imgpaste.wheel  # auto-select slot 0 (for tests)
```

No test framework / no `tests/` dir. Verification is done ad-hoc (see Testing below).

## Architecture

### Multi-process by design
The tray (`app.py`, runs `pystray.Icon.run()` on the main thread) **spawns the wheel,
cropper, and picker as separate subprocesses** (`subprocess.Popen([sys.executable, "-m",
"imgpaste.<x>"])`). This is deliberate: each overlay needs its own AppKit/Tk runloop,
which would clash with pystray's main runloop. There is no IPC back to the tray — each
subprocess does its own clipboard write + paste; capture passes the temp PNG path via argv.

### AppKit overlays (`wheel.py`, `cropper.py`) — why not Tk
Both are `NSPanel` (borderless + **nonactivating** + `clearColor`/`setOpaque_(False)`,
floating level). This is the only way to get **true transparency** (Tk on macOS renders
`systemTransparent` as black) **and not steal focus** (so synthetic paste lands in the
app the user was already in, no reactivation hack). `picker.py` is the Tk fallback used
only when not on macOS / AppKit import fails (`run()` dispatches).
Drawing is immediate-mode in `drawRect_` using `NSBezierPath`; hit-testing is manual by
coordinates (no NSButtons). `cropper.py` keeps **PIL** for image load + `_flatten()`
export (save/copy); AppKit is only display/interaction.

### Clipboard layer (`clipboard/`)
`__init__.py` dispatches by `sys.platform` to `macos.py` / `windows.py`. `copy_image()`
writes PNG image data to the pasteboard. NOTE: macOS auto-promotes png↔tiff on the
general pasteboard — you cannot put a single image representation; this is unavoidable
and is *not* the cause of any "pastes twice" bug (that's the receiving app reading
`files[]`+`items[]`, e.g. Electron/Chromium chat apps; native apps + Gemini paste once).

### config (`config.py`)
`Config` dataclass ↔ TOML at `~/.config/imgpaste/config.toml`, auto-serialized via
`asdict`/`_from_dict` (any new field is picked up automatically). `recent_images()` and
`images_in_dir()` (wheel) drive what the overlays show.

## Critical gotchas (will bite you)

- **Synthetic paste double-key.** A pynput keyboard `Listener` + `NSApp.run()` in the
  *same process* causes `pynput.Controller`-synthesized Cmd+V to fire **twice** (lingering
  CGEventTap re-injects). Both overlays hit this. **Always paste via
  `paste.paste_detached()`** (spawns a clean fresh-python subprocess), never `paste.paste()`
  directly, from any process that ran an AppKit loop or a pynput Listener.
- **Esc on nonactivating panels.** A nonactivating NSPanel never becomes key, so
  `keyDown_` won't fire for Esc. Both overlays use a **global pynput Esc Listener gated by
  `_mouse_over_win`/`_mouse_over_panel`** (so Esc in other apps doesn't close the overlay).
- **macOS Cmd+V via virtual keycode.** `paste.py` uses `KeyCode.from_vk(9)` on darwin —
  pynput doesn't apply the Command flag to the char `'v'`, so `Cmd+V` silently no-ops.
- **cropper coordinate transforms.** `CropView` is non-flipped (y-up). Shapes are stored
  **image-local, y-down, full-res** (`÷scale` on mouse input, `×scale` + y-flip on draw);
  `_flatten()` feeds the stored coords straight to PIL (also y-down). Keep these three
  consistent when touching draw/hit/export.
- **AppKit event loop teardown.** Overlays exit their runloop with
  `orderOut_` + `app.stop_` **plus posting a dummy `NSEventTypeApplicationDefined`** —
  `stop_` alone won't return from `run()` without an event to process.
- **`@objc.python_method`** is required on non-selector helpers of NSView/NSPanel
  subclasses (e.g. `_pt`, `_hit`), or PyObjC raises BadPrototype. Plain controller classes
  (`Cropper`, `AppKitWheel`) don't need it.

## Permissions (macOS)
Synthetic keys/mouse (paste, hotkeys, shake) need **Accessibility**; capture content needs
**Screen Recording**. Grant to Terminal/Python under System Settings → Privacy & Security.

## Testing pattern (no framework)
- **Pure helpers** (`wheel.slot_at_angle`, `images_in_dir`, `shake.count_reversals`) are
  importable and directly assertable.
- **Overlays**: launch the subprocess, `screencapture -x`, find the window via Quartz
  `CGWindowListCopyWindowInfo` (borderless windows often have empty name → match
  `owner=='Python'` + width), crop + Read the image. Drive interaction with `pynput`
  (AppKit accepts synthetic clicks; Tk overlays don't).
- **Paste/clipboard**: focus TextEdit via `osascript`, run the flow, then
  `count characters of text of front document` (1 image attachment = 1 char) to detect
  double-paste; `clipboard info` / `NSPasteboard.types()` to inspect pasteboard.
