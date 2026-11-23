"""The source editor widget: gutter, syntax, brackets, indentation and tabs."""

from __future__ import annotations

import bisect
import os
import re
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .highlighter import PascalHighlighter
from .theme import Color, Font, font_mono
from .widgets import FlatScrollbar


PAIRS = {"(": ")", "[": "]"}
CLOSERS = {")": "(", "]": "["}
OPENERS = set(PAIRS)
ALL_BRACKETS = OPENERS | set(CLOSERS)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------
@dataclass
class SourceText:
    text: str
    encoding: str
    encoding_label: str
    newline: str


def read_source_file(path: Path) -> SourceText:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        encoding, label = "utf-8-sig", "UTF-8 BOM"
    elif raw.startswith(b"\xff\xfe"):
        encoding, label = "utf-16", "UTF-16 LE"
    elif raw.startswith(b"\xfe\xff"):
        encoding, label = "utf-16", "UTF-16 BE"
    else:
        encoding, label = "utf-8", "UTF-8"
        for candidate, candidate_label in (("utf-8", "UTF-8"), ("gb18030", "GB18030")):
            try:
                raw.decode(candidate)
            except UnicodeDecodeError:
                continue
            encoding, label = candidate, candidate_label
            break
        else:
            encoding, label = "cp1252", "CP1252"

    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        text = raw.decode(encoding, errors="replace")

    if "\r\n" in text:
        newline = "\r\n"
    elif "\r" in text and "\n" not in text:
        newline = "\r"
    else:
        newline = "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return SourceText(text=text, encoding=encoding, encoding_label=label, newline=newline)


def write_source_file(path: Path, text: str, encoding: str, newline: str) -> None:
    data = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    raw = data.encode(encoding, errors="replace")
    path.write_bytes(raw)


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------
class Editor(tk.Frame):
    def __init__(
        self,
        master,
        *,
        font_size: int = 11,
        tab_width: int = 4,
        use_spaces: bool = True,
        on_state_change: Callable[["Editor"], None] | None = None,
        on_cursor: Callable[["Editor"], None] | None = None,
        on_content_change: Callable[["Editor"], None] | None = None,
    ) -> None:
        super().__init__(master, bg=Color.EDITOR_BG, bd=0, highlightthickness=0)
        self.path: Path | None = None
        self.display_name = "未命名.pas"
        self.encoding = "utf-8"
        self.encoding_label = "UTF-8"
        self.newline = "\r\n"
        self.dirty = False
        self._on_state_change = on_state_change
        self._on_cursor = on_cursor
        self._on_content_change = on_content_change
        self.font_size = font_size
        self.tab_width = tab_width
        self.use_spaces = use_spaces
        self._loading = False
        self._highlight_job: str | None = None
        self._gutter_job: str | None = None
        self._cursor_job: str | None = None
        self._bracket_job: str | None = None

        self.code_font = tkfont.Font(
            root=self, family=Font.MONO, size=font_size, weight="normal"
        )
        self.gutter_font = tkfont.Font(
            root=self, family=Font.MONO, size=max(8, font_size - 2)
        )

        self.gutter = tk.Canvas(
            self,
            width=58,
            bg=Color.GUTTER_BG,
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        self.gutter.pack(side="left", fill="y")

        self.scrollbar = FlatScrollbar(self, command=self._scroll_text, bg=Color.EDITOR_BG)
        self.scrollbar.pack(side="right", fill="y")

        self.text = tk.Text(
            self,
            wrap="none",
            undo=True,
            maxundo=-1,
            autoseparators=True,
            font=self.code_font,
            bg=Color.EDITOR_BG,
            fg=Color.TEXT,
            insertbackground=Color.CARET,
            insertwidth=2,
            selectbackground=Color.SELECTION,
            selectforeground=Color.TEXT,
            inactiveselectbackground=Color.SELECTION_INACTIVE,
            highlightthickness=0,
            bd=0,
            relief="flat",
            padx=14,
            pady=10,
            spacing1=1,
            spacing3=1,
            tabs=self._tab_stops(),
            yscrollcommand=self._on_yscroll,
            takefocus=1,
        )
        self.text.pack(side="left", fill="both", expand=True)
        self.text.configure(exportselection=True)

        self.text.tag_configure("current_line", background=Color.CURRENT_LINE)
        self.text.tag_configure(
            "bracket_match",
            background=Color.MATCH_BG,
            foreground=Color.MATCH_FG,
        )
        self.text.tag_configure(
            "bracket_unmatched",
            background=Color.UNMATCHED_BG,
            foreground=Color.UNMATCHED_FG,
        )
        self.text.tag_raise("current_line")
        self.highlighter = PascalHighlighter(self.text, font_size)

        self._bind_events()
        self._update_gutter_font()
        self.after_idle(self._redraw_gutter)

    # -- construction helpers ----------------------------------------------
    def _bind_events(self) -> None:
        self.text.bind("<<Modified>>", self._on_modified, add="+")
        self.text.bind("<KeyRelease>", self._on_key_release, add="+")
        self.text.bind("<ButtonRelease-1>", self._on_click_release, add="+")
        self.text.bind("<B1-Motion>", self._on_click_release, add="+")
        self.text.bind("<Button-1>", lambda _e: self.after_idle(self._after_cursor), add="+")
        self.text.bind("<KeyPress>", self._on_keypress, add="+")
        self.text.bind("<Return>", self._on_return, add="+")
        self.text.bind("<KP_Enter>", self._on_return, add="+")
        self.text.bind("<Tab>", self._on_tab, add="+")
        self.text.bind("<Shift-Tab>", self._on_shift_tab, add="+")
        self.text.bind("<ISO_Left_Tab>", self._on_shift_tab, add="+")
        self.text.bind("<BackSpace>", self._on_backspace, add="+")
        self.text.bind("<Configure>", lambda _e: self._schedule_gutter(10), add="+")
        self.text.bind("<FocusIn>", lambda _e: self._after_cursor(), add="+")
        self.gutter.bind("<MouseWheel>", self._gutter_wheel)
        self.text.bind("<<Undo>>", lambda _e: self._schedule_highlight(20), add="+")
        self.text.bind("<<Redo>>", lambda _e: self._schedule_highlight(20), add="+")
        self.text.bind("<<Paste>>", lambda _e: self._schedule_highlight(20), add="+")

    def _tab_stops(self) -> tuple[str, ...]:
        # Tk's text widget wants explicit pixel stops.  Generate enough stops
        # to cover very long lines; the font is fixed-width.
        space = max(1, self.code_font.measure(" "))
        width = max(1, round(space * self.tab_width))
        return tuple(str(i * width) for i in range(1, 513))

    def _scroll_text(self, *args) -> None:
        self.text.yview(*args)
        self._schedule_gutter(5)

    def _on_yscroll(self, first, last) -> None:
        self.scrollbar.set(first, last)
        self._schedule_gutter(10)

    # -- cursor / state tracking -------------------------------------------
    def _after_cursor(self) -> None:
        if self._cursor_job:
            try:
                self.after_cancel(self._cursor_job)
            except tk.TclError:
                pass
        self._cursor_job = self.after_idle(self._apply_cursor_state)

    def _apply_cursor_state(self) -> None:
        self._cursor_job = None
        try:
            info = self.text.index("insert")
        except tk.TclError:
            return
        line, col = (int(part) for part in info.split("."))
        self._paint_current_line(line)
        self._schedule_bracket(10)
        if self._on_cursor is not None:
            try:
                end_line = int(self.text.index("end-1c").split(".")[0])
                chars = len(self.text.get("1.0", "end-1c"))
                self._on_cursor(self, line, col + 1, end_line, chars)
            except tk.TclError:
                pass
        self._schedule_gutter(10)

    def _paint_current_line(self, line: int) -> None:
        self.text.tag_remove("current_line", "1.0", "end")
        start = f"{line}.0"
        end = f"{line}.end+1c"
        self.text.tag_add("current_line", start, end)
        self.text.tag_lower("current_line")

    def _on_modified(self, _event=None) -> None:
        try:
            modified = bool(self.text.edit_modified())
        except tk.TclError:
            return
        if self._loading:
            return
        if not modified:
            return
        self.text.edit_modified(False)
        self.set_dirty(True)
        self._schedule_highlight(35)
        self._schedule_gutter(20)
        if self._on_content_change is not None:
            self._on_content_change(self)

    def _on_key_release(self, event) -> None:
        if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"):
            return
        self._after_cursor()

    def _on_click_release(self, _event=None) -> None:
        self.after_idle(self._after_cursor)

    def set_dirty(self, dirty: bool) -> None:
        if dirty != self.dirty:
            self.dirty = dirty
            if self._on_state_change is not None:
                self._on_state_change(self)

    def notify_cursor(self) -> None:
        self._after_cursor()

    # -- syntax / brackets --------------------------------------------------
    def _schedule_highlight(self, delay: int = 40) -> None:
        if self._highlight_job:
            try:
                self.after_cancel(self._highlight_job)
            except tk.TclError:
                pass
        self._highlight_job = self.after(delay, self._run_highlight)

    def _run_highlight(self) -> None:
        self._highlight_job = None
        self.highlighter.highlight()
        self._schedule_bracket(0)
        self._schedule_gutter(10)

    def _schedule_bracket(self, delay: int = 20) -> None:
        if self._bracket_job:
            try:
                self.after_cancel(self._bracket_job)
            except tk.TclError:
                pass
        self._bracket_job = self.after(delay, self._update_brackets)

    def _update_brackets(self) -> None:
        self._bracket_job = None
        self.text.tag_remove("bracket_match", "1.0", "end")
        self.text.tag_remove("bracket_unmatched", "1.0", "end")
        try:
            src = self.text.get("1.0", "end-1c")
            insert = self.text.index("insert")
        except tk.TclError:
            return
        mask = self.highlighter.masked
        if len(mask) < len(src) + 1 or len(self.highlighter.line_starts) == 0:
            return
        offset = self.highlighter.offset(insert)
        chosen: tuple[int, str, int] | None = None
        if offset > 0 and src[offset - 1] in ALL_BRACKETS and not mask[offset - 1]:
            chosen = (offset - 1, src[offset - 1], -1)
        elif offset < len(src) and src[offset] in ALL_BRACKETS and not mask[offset]:
            chosen = (offset, src[offset], +1)
        if chosen is None:
            return
        pos, char, direction = chosen
        if char in PAIRS:
            partner = self._find_forward(src, mask, pos, char, PAIRS[char])
        else:
            partner = self._find_backward(src, mask, pos, char, CLOSERS[char])
        if partner is None:
            self._tag_bracket("bracket_unmatched", pos)
        else:
            self._tag_bracket("bracket_match", pos)
            self._tag_bracket("bracket_match", partner)

    def _tag_bracket(self, tag: str, offset: int) -> None:
        index = self.highlighter.index(offset)
        self.text.tag_add(tag, index, f"{index}+1c")
        self.text.tag_raise(tag)

    @staticmethod
    def _find_forward(
        src: str, mask: bytearray, pos: int, open_char: str, close_char: str
    ) -> int | None:
        depth = 0
        i = pos + 1
        n = len(src)
        while i < n:
            if mask[i]:
                i += 1
                continue
            c = src[i]
            if c == open_char:
                depth += 1
            elif c == close_char:
                if depth == 0:
                    return i
                depth -= 1
            i += 1
        return None

    @staticmethod
    def _find_backward(
        src: str, mask: bytearray, pos: int, close_char: str, open_char: str
    ) -> int | None:
        depth = 0
        i = pos - 1
        while i >= 0:
            if mask[i]:
                i -= 1
                continue
            c = src[i]
            if c == close_char:
                depth += 1
            elif c == open_char:
                if depth == 0:
                    return i
                depth -= 1
            i -= 1
        return None

    # -- editing behaviour --------------------------------------------------
    def _on_keypress(self, event) -> str | None:
        if event.state & 0x4:  # Control
            return None
        if event.state & 0x20000:  # Alt
            return None
        char = event.char
        if char in PAIRS:
            selected = self.text.tag_ranges("sel")
            if selected:
                value = self.text.get(selected[0], selected[1])
                self.text.delete(selected[0], selected[1])
                self.text.insert("insert", char + value + PAIRS[char])
                self.text.mark_set("insert", "insert-1c")
            else:
                self.text.insert("insert", char + PAIRS[char])
                self.text.mark_set("insert", "insert-1c")
            self.text.see("insert")
            self._after_cursor()
            return "break"
        if char in CLOSERS:
            if self.text.tag_ranges("sel"):
                return None
            following = self.text.get("insert", "insert+1c")
            if following == char:
                self.text.mark_set("insert", "insert+1c")
                self._after_cursor()
                return "break"
        return None

    def _on_backspace(self, _event=None) -> str | None:
        if self.text.tag_ranges("sel"):
            return None
        before = self.text.get("insert-1c", "insert")
        after = self.text.get("insert", "insert+1c")
        if before in PAIRS and after == PAIRS[before]:
            self.text.delete("insert-1c", "insert+1c")
            self._after_cursor()
            return "break"
        return None

    def _leading_ws(self, index: str) -> str:
        line = self.text.get(f"{index} linestart", index)
        return re.match(r"[ \t]*", line).group(0)

    def _indent_unit(self) -> str:
        return " " * self.tab_width if self.use_spaces else "\t"

    def _on_return(self, _event=None) -> str:
        selected = self.text.tag_ranges("sel")
        if selected:
            self.text.delete(selected[0], selected[1])
        before = self.text.get("insert linestart", "insert")
        base = re.match(r"[ \t]*", before).group(0)
        stripped = before.strip()
        extra = ""
        if stripped and re.search(
            r"(?:\bbegin|\bthen|\belse|\bdo|\brepeat|\brecord|\btry|\bfinally|\bexcept|\bcase|\bof)\s*$",
            stripped,
            re.IGNORECASE,
        ):
            extra = self._indent_unit()
        self.text.insert("insert", "\n" + base + extra)
        self.text.see("insert")
        self._after_cursor()
        return "break"

    def _selected_line_numbers(self) -> list[int] | None:
        ranges = self.text.tag_ranges("sel")
        if not ranges:
            return None
        start_index = self.text.index(ranges[0])
        end_index = self.text.index(ranges[1])
        first = int(start_index.split(".")[0])
        last = int(end_index.split(".")[0])
        # A selection ending exactly at the beginning of a line should not
        # affect that line.
        try:
            if end_index.split(".")[1] == "0" and last > first:
                last -= 1
        except (IndexError, ValueError):
            pass
        return list(range(first, last + 1))

    def _on_tab(self, _event=None) -> str:
        lines = self._selected_line_numbers()
        if lines:
            unit = self._indent_unit()
            first, last = lines[0], lines[-1]
            for line in reversed(lines):
                self.text.insert(f"{line}.0", unit)
            self.text.tag_remove("sel", "1.0", "end")
            self.text.tag_add("sel", f"{first}.0", f"{last}.end")
        else:
            if self.use_spaces:
                line, col = (int(value) for value in self.text.index("insert").split("."))
                count = self.tab_width - (col % self.tab_width)
                self.text.insert("insert", " " * count)
            else:
                self.text.insert("insert", "\t")
            self.text.see("insert")
        self._after_cursor()
        return "break"

    def _on_shift_tab(self, _event=None) -> str:
        lines = self._selected_line_numbers() or [
            int(self.text.index("insert").split(".")[0])
        ]
        for line in reversed(lines):
            start = f"{line}.0"
            prefix = self.text.get(start, f"{line}.{self.tab_width}")
            if prefix.startswith("\t"):
                self.text.delete(start, f"{start}+1c")
            else:
                spaces = len(prefix) - len(prefix.lstrip(" "))
                remove = min(spaces, self.tab_width)
                if remove:
                    self.text.delete(start, f"{start}+{remove}c")
        self._after_cursor()
        return "break"

    # -- gutter -------------------------------------------------------------
    def _update_gutter_font(self) -> None:
        self.gutter_font.configure(size=max(8, self.font_size - 2))
        self.gutter.configure(width=max(50, self.gutter_font.measure("0000") + 24))

    def _schedule_gutter(self, delay: int = 16) -> None:
        if self._gutter_job:
            try:
                self.after_cancel(self._gutter_job)
            except tk.TclError:
                pass
        self._gutter_job = self.after(delay, self._redraw_gutter)

    def _redraw_gutter(self) -> None:
        self._gutter_job = None
        canvas = self.gutter
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        canvas.create_rectangle(0, 0, width, height, fill=Color.GUTTER_BG, outline="")
        try:
            cursor_line = int(self.text.index("insert").split(".")[0])
            start_line = int(self.text.index("@0,0").split(".")[0])
        except (tk.TclError, ValueError):
            return
        line = start_line
        drawn = 0
        while drawn < 4000:
            dline = self.text.dlineinfo(f"{line}.0")
            if dline is None:
                break
            y, h = dline[1], dline[3]
            if y > height:
                break
            if y + h >= 0:
                active = line == cursor_line
                canvas.create_text(
                    width - 12,
                    y + h // 2,
                    text=str(line),
                    anchor="e",
                    font=self.gutter_font,
                    fill=Color.ACCENT if active else Color.TEXT_FAINT,
                )
                if active:
                    canvas.create_rectangle(0, max(0, y), 3, min(height, y + h), fill=Color.ACCENT, outline="")
            line += 1
            drawn += 1
        canvas.create_line(width - 1, 0, width - 1, height, fill=Color.BORDER_SOFT)

    def _gutter_wheel(self, event) -> None:
        self.text.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self._schedule_gutter(5)

    # -- settings -----------------------------------------------------------
    def set_tab_width(self, width: int) -> None:
        self.tab_width = max(1, min(8, int(width)))
        self.text.configure(tabs=self._tab_stops())
        self._schedule_gutter(5)

    def set_use_spaces(self, use_spaces: bool) -> None:
        self.use_spaces = bool(use_spaces)

    def set_font_size(self, size: int) -> None:
        self.font_size = max(8, min(24, int(size)))
        self.code_font.configure(size=self.font_size)
        self.text.configure(font=self.code_font, tabs=self._tab_stops())
        self._update_gutter_font()
        self.highlighter.set_font_size(self.font_size)
        self._schedule_highlight(10)
        self._schedule_gutter(20)

    # -- document -----------------------------------------------------------
    def set_content(self, text: str) -> None:
        self._loading = True
        try:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
            self.text.edit_reset()
            self.text.edit_modified(False)
            self.text.mark_set("insert", "1.0")
            self.text.see("1.0")
            self.text.tag_remove("sel", "1.0", "end")
        finally:
            self._loading = False
        self.dirty = False
        self._run_highlight()
        self._apply_cursor_state()
        self._redraw_gutter()

    def get_content(self) -> str:
        return self.text.get("1.0", "end-1c")

    def mark_saved(self) -> None:
        self.text.edit_modified(False)
        self.set_dirty(False)

    def focus_editor(self) -> None:
        self.text.focus_set()

    def scroll_to(self, line: int, col: int = 1) -> None:
        try:
            last_line = int(self.text.index("end-1c").split(".")[0])
        except (tk.TclError, ValueError):
            last_line = 1
        line = max(1, min(last_line, int(line)))
        col = max(1, int(col))
        index = f"{line}.{col - 1}"
        self.text.mark_set("insert", index)
        self.text.tag_remove("sel", "1.0", "end")
        self.text.see(index)
        self.focus_editor()
        self._after_cursor()

    def line_count(self) -> int:
        try:
            return int(self.text.index("end-1c").split(".")[0])
        except (tk.TclError, ValueError):
            return 1

    def char_count(self) -> int:
        try:
            return len(self.text.get("1.0", "end-1c"))
        except tk.TclError:
            return 0

    def destroy(self) -> None:
        for job in (self._highlight_job, self._gutter_job, self._cursor_job, self._bracket_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        super().destroy()
