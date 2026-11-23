"""A small dark popup menu drawn entirely with Tk primitives.

Tk's native Windows popup menus ignore ``bg``/``fg`` and have rounded system
chrome.  Pascal Box uses this menu instead so every piece of the interface
stays rectangular and in the same palette.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Callable

from .theme import Color, Font, font_ui


@dataclass
class _Item:
    label: str = ""
    accelerator: str = ""
    command: Callable[[], None] | None = None
    separator: bool = False


class SharpMenu:
    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self.items: list[_Item] = []
        self.window: tk.Toplevel | None = None
        self._rows: list[dict] = []
        self._selected = -1
        self._label_font = tkfont.Font(
            root=master, family=Font.UI, size=9
        )
        self._accel_font = tkfont.Font(
            root=master, family="Consolas", size=8
        )

    # -- construction -------------------------------------------------------
    def add_command(
        self,
        label: str,
        *,
        accelerator: str = "",
        command: Callable[[], None] | None = None,
    ) -> None:
        self.items.append(_Item(label=label, accelerator=accelerator, command=command))

    def add_separator(self) -> None:
        self.items.append(_Item(separator=True))

    # -- open / close -------------------------------------------------------
    def post(self, x: int, y: int) -> None:
        self.unpost()
        window = tk.Toplevel(self.master)
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg=Color.BORDER_BRIGHT)
        window.attributes("-topmost", True)
        self.window = window
        self._selected = -1
        self._rows = []

        content = tk.Frame(window, bg=Color.CHROME)
        content.pack(padx=1, pady=1)

        width = self._measure_width()
        for index, item in enumerate(self.items):
            if item.separator:
                gap = tk.Frame(content, bg=Color.CHROME, height=7)
                gap.pack(fill="x")
                tk.Frame(gap, bg=Color.BORDER_SOFT, height=1).pack(
                    fill="x", padx=10, pady=3
                )
                self._rows.append({"separator": True, "widgets": [gap]})
            else:
                row = tk.Frame(
                    content,
                    bg=Color.CHROME,
                    height=30,
                    width=width,
                    cursor="hand2",
                )
                row.pack(fill="x")
                row.pack_propagate(False)
                accent = tk.Frame(row, bg=Color.CHROME, width=2)
                accent.pack(side="left", fill="y")
                label = tk.Label(
                    row,
                    text=item.label,
                    bg=Color.CHROME,
                    fg=Color.TEXT,
                    font=self._label_font,
                    anchor="w",
                    padx=10,
                    cursor="hand2",
                )
                label.pack(side="left", fill="both", expand=True)
                accel = tk.Label(
                    row,
                    text=item.accelerator,
                    bg=Color.CHROME,
                    fg=Color.TEXT_FAINT,
                    font=self._accel_font,
                    anchor="e",
                    padx=10,
                    cursor="hand2",
                )
                accel.pack(side="right", fill="y")
                row_data = {
                    "separator": False,
                    "row": row,
                    "accent": accent,
                    "label": label,
                    "accel": accel,
                    "item": item,
                    "index": index,
                }
                self._rows.append(row_data)
                for widget in (row, label, accel):
                    widget.bind("<Enter>", lambda _e, data=row_data: self._hover(data))
                    widget.bind("<Leave>", lambda _e, data=row_data: self._unhover(data))
                    widget.bind(
                        "<Button-1>",
                        lambda _e, data=row_data: self._activate(data),
                    )

        window.update_idletasks()
        height = window.winfo_reqheight()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        pos_x = min(max(0, x), max(0, screen_w - width - 2))
        pos_y = min(max(0, y), max(0, screen_h - height - 2))
        window.geometry(f"{width + 2}x{height}+{pos_x}+{pos_y}")
        window.deiconify()
        window.lift()
        try:
            window.grab_set()
        except tk.TclError:
            pass
        try:
            window.focus_force()
        except tk.TclError:
            pass
        window.bind("<Escape>", lambda _e: self.unpost())
        window.bind("<FocusOut>", lambda _e: self.unpost())
        window.bind("<Down>", lambda _e: self._move(1))
        window.bind("<Up>", lambda _e: self._move(-1))
        window.bind("<Return>", lambda _e: self._activate_selected())
        window.bind("<Button-1>", lambda _e: self.unpost(), add="+")

    def unpost(self) -> None:
        window = self.window
        self.window = None
        self._selected = -1
        if window is not None:
            try:
                window.grab_release()
            except tk.TclError:
                pass
            try:
                window.destroy()
            except tk.TclError:
                pass

    # -- interactions -------------------------------------------------------
    def _measure_width(self) -> int:
        width = 216
        for item in self.items:
            if item.separator:
                continue
            needed = (
                self._label_font.measure(item.label)
                + self._accel_font.measure(item.accelerator)
                + 58
            )
            width = max(width, needed)
        return min(360, width)

    def _paint_row(self, row_info: dict, active: bool) -> None:
        if row_info.get("separator"):
            return
        bg = Color.BTN_HOVER if active else Color.CHROME
        fg = Color.TEXT if active else Color.TEXT
        accent = Color.ACCENT if active else Color.CHROME
        row_info["row"].configure(bg=bg)
        row_info["label"].configure(bg=bg, fg=fg)
        row_info["accel"].configure(bg=bg, fg=Color.TEXT_DIM if active else Color.TEXT_FAINT)
        row_info["accent"].configure(bg=accent)

    def _hover(self, row_info: dict) -> None:
        if row_info.get("separator"):
            return
        self._paint_row(row_info, True)

    def _unhover(self, row_info: dict) -> None:
        if row_info.get("separator"):
            return
        selected = (
            0 <= self._selected < len(self._rows)
            and self._rows[self._selected] is row_info
        )
        self._paint_row(row_info, selected)

    def _activate(self, row_info: dict) -> str:
        item = row_info.get("item")
        self.unpost()
        if item is not None and item.command is not None:
            try:
                self.master.after_idle(item.command)
            except tk.TclError:
                pass
        return "break"

    def _move(self, delta: int) -> str:
        selectable = [
            i for i, row in enumerate(self._rows) if not row.get("separator")
        ]
        if not selectable:
            return "break"
        if self._selected in selectable:
            position = selectable.index(self._selected)
            position = (position + delta) % len(selectable)
        else:
            position = 0 if delta >= 0 else len(selectable) - 1
        new_index = selectable[position]
        if 0 <= self._selected < len(self._rows):
            old = self._rows[self._selected]
            self._paint_row(old, False)
        self._selected = new_index
        self._paint_row(self._rows[new_index], True)
        return "break"

    def _activate_selected(self) -> str:
        if 0 <= self._selected < len(self._rows):
            row_info = self._rows[self._selected]
            if not row_info.get("separator"):
                self._activate(row_info)
        return "break"
