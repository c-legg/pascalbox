"""Pascal Box entry point."""

from __future__ import annotations

import argparse
import ctypes
import os
import sys

from pascalbox import __version__


def _enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "PascalBox.Desktop.1"
        )
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Pascal Box",
        description="轻量 Object Pascal 桌面编辑器",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="启动时打开的源文件；不存在的路径可作为新文件名打开",
    )
    parser.add_argument("-v", "--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _enable_windows_dpi_awareness()
    from pascalbox.app import PascalBox

    app = PascalBox(args.files)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
