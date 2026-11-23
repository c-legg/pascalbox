"""Small JSON-backed preferences store."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "tab_width": 4,
    "use_spaces": True,
    "font_size": 11,
    "last_dir": "",
    "output_height": 220,
    "output_visible": True,
    "theme": "dark",
}


def _is_compiled() -> bool:
    """True inside PyInstaller or Nuitka builds."""
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def _settings_path() -> Path:
    """Keep preferences next to the IDE executable (or main.py in a source run)."""
    if _is_compiled():
        # ``sys.argv[0]`` is the launcher path for both standalone and onefile
        # Nuitka builds; ``sys.executable`` can point into a onefile temp dir.
        executable = Path(sys.argv[0]).resolve()
        root = executable.parent if executable.is_file() else Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent.parent
    return root / "settings.json"


class Settings:
    def __init__(self) -> None:
        self.path = _settings_path()
        self._data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in DEFAULTS:
                    if key in raw:
                        self._data[key] = raw[key]
        except (OSError, ValueError, TypeError):
            pass
        self._sanitize()

    def _sanitize(self) -> None:
        try:
            self._data["tab_width"] = max(1, min(8, int(self._data["tab_width"])))
        except (TypeError, ValueError):
            self._data["tab_width"] = 4
        try:
            self._data["font_size"] = max(8, min(24, int(self._data["font_size"])))
        except (TypeError, ValueError):
            self._data["font_size"] = 11
        try:
            self._data["output_height"] = max(110, min(640, int(self._data["output_height"])))
        except (TypeError, ValueError):
            self._data["output_height"] = 220
        self._data["use_spaces"] = bool(self._data["use_spaces"])
        self._data["output_visible"] = bool(self._data["output_visible"])
        self._data["theme"] = "light" if str(self._data.get("theme")).lower() == "light" else "dark"

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, self.path)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        self._data[key] = value
        if save:
            self.save()
