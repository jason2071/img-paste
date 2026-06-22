"""Entry point + subcommand router.

  python -m imgpaste            -> tray app
  python -m imgpaste wheel      -> radial image wheel
  python -m imgpaste cropper X  -> editor on image X
  python -m imgpaste cropper --capture
  python -m imgpaste picker     -> Tk grid fallback
  python -m imgpaste paste [d]  -> synthetic Cmd+V (optional delay)

Frozen PyInstaller binary re-execs itself with these subcommands (see _exec.spawn),
so absolute imports are required — a bundled __main__ has no parent package for
relative imports.
"""

import sys


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else None

    if cmd == "wheel":
        from imgpaste.wheel import run
        run()
    elif cmd == "cropper":
        rest = argv[1:]
        cap = "--capture" in rest
        files = [a for a in rest if not a.startswith("-")]
        from imgpaste.cropper import run
        run(files[0] if files else None, cap)
    elif cmd == "picker":
        from imgpaste.picker import run
        run()
    elif cmd == "paste":
        import time
        from imgpaste import paste
        if len(argv) > 1:
            try:
                time.sleep(float(argv[1]))
            except ValueError:
                pass
        paste.paste()
    else:
        from imgpaste.app import main as app_main
        app_main()


if __name__ == "__main__":
    main()
