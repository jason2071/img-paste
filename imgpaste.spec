# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — build imgpaste as a macOS menu-bar .app (LSUIElement)."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
# pyobjc frameworks + tray/input libs ต้อง collect ให้ครบ (namespace/dynamic import)
for pkg in ("pystray", "pynput", "objc", "AppKit", "Foundation",
            "Quartz", "watchdog", "PIL"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass
hiddenimports += [
    # router ใน __main__.py lazy-import โมดูลเหล่านี้ -> ต้องบังคับ bundle
    "imgpaste.app",
    "imgpaste.wheel",
    "imgpaste.cropper",
    "imgpaste.picker",
    "imgpaste.paste",
    "imgpaste._exec",
    "imgpaste.clipboard.macos",
    "imgpaste.clipboard.windows",
    "PyObjCTools.AppHelper",
]

a = Analysis(
    ["imgpaste/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="imgpaste",
    debug=False,
    strip=False,
    upx=False,
    console=False,            # windowed (no terminal)
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name="imgpaste",
)
app = BUNDLE(
    coll,
    name="SnapPaste.app",
    icon="assets/imgpaste.icns",
    bundle_identifier="com.snappaste.app",
    info_plist={
        "LSUIElement": True,                 # menu-bar only, ไม่ขึ้น Dock
        "CFBundleName": "SnapPaste",
        "CFBundleDisplayName": "SnapPaste",
        "CFBundleShortVersionString": "0.2.5",
        "NSHighResolutionCapable": True,
    },
)
