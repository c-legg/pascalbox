"""Inline find and replace bar for the source editor."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable

from .theme import Color, font_ui
from .widgets import FlatButton, Tooltip

if TYPE_CHECKING:
    from .editor import Editor


class SearchBar(tk.Frame):
    """A compact, square-cornered find/replace panel over the editor."""

    MAX_MATCHES = 20000
    MAX_HIGHLIGHTS = 4000

    def __init__(
        self,
        master: tk.Misc,
        *,
        get_editor: Callable[[], "Editor | None"],
        set_status: Callable[[str, str], None],
    ) -> None:
        super().__init__(
            master,
            bg=Color.CHROME,
            bd=0,
            highlightthickness=1,
            highlightbackground=Color.BORDER_BRIGHT,
        )
        self._get_editor = get_editor
        self._set_status = set_status
        self.visible = False
        self.replace_mode = False
        self.case_sensitive = False
        self.whole_word = False
        self.matches: list[tuple[str, str]] = []
        self.current: tuple[str, str] | None = None
        self._tagged_editor: "Editor | None" = None
        self._refresh_job: str | None = None
        self._count_var = tk.IntVar(master=self)
        self.find_var = tk.StringVar(master=self)
        self.replace_var = tk.StringVar(master=self)
        self.find_var.trace_add("write", self._on_query_changed)
        self._build_widgets()
        self.place_forget()

    # -- construction -------------------------------------------------------
    def _build_widgets(self) -> None:
        tk.Frame(self, bg=Color.ACCENT, height=2, bd=0, highlightthickness=0).pack(
            fill="x"
        )
        body = tk.Frame(self, bg=Color.CHROME, padx=10, pady=8)
        body.pack(fill="both", expand=True)

        find_row = tk.Frame(body, bg=Color.CHROME)
        find_row.pack(fill="x")
        self._row_label(find_row, "查找")
        self.find_entry = self._entry(find_row, self.find_var)
        self.case_toggle = self._toggle(
            find_row, "Aa", "区分大小写", self.toggle_case
        )
        self.word_toggle = self._toggle(
            find_row, "全字", "全字匹配", self.toggle_whole_word
        )
        self.count_label = tk.Label(
            find_row,
            text="",
            width=9,
            anchor="e",
            bg=Color.CHROME,
            fg=Color.TEXT_FAINT,
            font=("Consolas", 8),
        )
        self.count_label.pack(side="left", padx=(8, 4))
        self._tool_button(find_row, "↑", self.find_previous).pack(
            side="left", padx=(0, 3)
        )
        self._tool_button(find_row, "↓", self.find_next).pack(
            side="left", padx=(0, 3)
        )
        self._tool_button(find_row, "×", self.hide, border=False).pack(side="left")

        self._divider = tk.Frame(body, bg=Color.BORDER_SOFT, height=1)
        self.replace_row = tk.Frame(body, bg=Color.CHROME)
        self._row_label(self.replace_row, "替换")
        self.replace_entry = self._entry(self.replace_row, self.replace_var)
        FlatButton(
            self.replace_row,
            text="替换",
            kind="secondary",
            command=self.replace_current,
            padx=10,
            pady=2,
        ).pack(side="left", padx=(0, 4))
        FlatButton(
            self.replace_row,
            text="全部替换",
            kind="secondary",
            command=self.replace_all,
            padx=10,
            pady=2,
        ).pack(side="left")

        self._style_toggles()
        for widget in (self, self.find_entry, self.replace_entry,
                       self.case_toggle, self.word_toggle):
            widget.bind("<Escape>", self._on_escape)

        self.find_entry.bind("<Return>", lambda _e: self._return_find(True))
        self.find_entry.bind("<KP_Enter>", lambda _e: self._return_find(True))
        self.find_entry.bind("<Shift-Return>", lambda _e: self._return_find(False))
        self.replace_entry.bind("<Return>", lambda _e: self._return_replace())
        self.replace_entry.bind("<KP_Enter>", lambda _e: self._return_replace())
        for entry in (self.find_entry, self.replace_entry):
            entry.bind(
                "<Control-f>", lambda _e: self._rebind_shortcut(self.show_find)
            )
            entry.bind(
                "<Control-F>", lambda _e: self._rebind_shortcut(self.show_find)
            )
            entry.bind(
                "<Control-h>", lambda _e: self._rebind_shortcut(self.show_replace)
            )
            entry.bind(
                "<Control-H>", lambda _e: self._rebind_shortcut(self.show_replace)
            )

    @staticmethod
    def _rebind_shortcut(action: Callable[[], None]) -> str:
        action()
        return "break"

    def _row_label(self, parent, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            width=4,
            anchor="w",
            bg=Color.CHROME,
            fg=Color.TEXT_DIM,
            font=font_ui(8, "bold"),
        ).pack(side="left")

    def _entry(self, parent, variable: tk.StringVar) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            width=24,
            bg=Color.INPUT_BG,
            fg=Color.TEXT,
            insertbackground=Color.CARET,
            selectbackground=Color.SELECTION,
            selectforeground=Color.TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=Color.BORDER,
            highlightcolor=Color.ACCENT,
            font=font_ui(9),
            exportselection=False,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=3)
        return entry

    def _toggle(
        self, parent, text: str, tooltip: str, command: Callable[[], None]
    ) -> tk.Label:
        label = tk.Label(
            parent,
            text=text,
            bg=Color.BTN_BG,
            fg=Color.TEXT_DIM,
            padx=6,
            pady=3,
            bd=0,
            highlightthickness=1,
            highlightbackground=Color.BORDER,
            font=("Consolas", 8),
            cursor="hand2",
            takefocus=1,
        )
        label.pack(side="left", padx=(6, 0))
        label.bind("<Button-1>", lambda _e: command())
        label.bind("<Return>", lambda _e: command())
        label.bind("<space>", lambda _e: command())
        Tooltip(label, tooltip)
        return label

    def _tool_button(
        self, parent, text: str, command: Callable[[], None], *, border: bool = True
    ) -> FlatButton:
        return FlatButton(
            parent,
            text=text,
            kind="ghost" if not border else "secondary",
            command=command,
            padx=7,
            pady=2,
            border=border,
            font=("Consolas", 9),
        )

    # -- state --------------------------------------------------------------
    def _style_toggles(self) -> None:
        for widget, active in (
            (self.case_toggle, self.case_sensitive),
            (self.word_toggle, self.whole_word),
        ):
            widget.configure(
                bg=Color.ACCENT if active else Color.BTN_BG,
                fg=Color.TEXT_INVERSE if active else Color.TEXT_DIM,
                activebackground=Color.ACCENT if active else Color.BTN_HOVER,
                activeforeground=Color.TEXT_INVERSE if active else Color.TEXT,
                highlightbackground=Color.ACCENT if active else Color.BORDER,
            )

    def refresh_theme(self) -> None:
        self.configure(
            bg=Color.CHROME, highlightbackground=Color.BORDER_BRIGHT
        )
        for entry in (self.find_entry, self.replace_entry):
            entry.configure(
                bg=Color.INPUT_BG,
                fg=Color.TEXT,
                insertbackground=Color.CARET,
                selectbackground=Color.SELECTION,
                selectforeground=Color.TEXT,
                highlightbackground=Color.BORDER,
                highlightcolor=Color.ACCENT,
            )
        self.count_label.configure(bg=Color.CHROME)
        self._style_toggles()
        self._update_count()
        editor = self._tagged_editor
        if editor is None or not self._widget_exists(editor):
            return
        self._ensure_tags(editor)
        if self.visible:
            self._apply_tags(editor, self.matches, self.current)

    @staticmethod
    def _widget_exists(widget: tk.Misc) -> bool:
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    # -- show / hide --------------------------------------------------------
    def show(self, replace: bool = False) -> None:
        editor = self._get_editor()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return
        opening = not self.visible
        if opening:
            self._tagged_editor = editor
            selected = self._selected_text(editor)
            if selected:
                self.find_var.set(selected)
            self.place(relx=1.0, x=-18, y=12, anchor="ne")
            self.visible = True
        self.set_replace_mode(replace if opening else (replace or self.replace_mode))
        self.lift()
        self.find_entry.focus_set()
        self.find_entry.selection_range(0, "end")
        self._refresh_matches()

    def show_find(self) -> None:
        self.show(replace=False)

    def show_replace(self) -> None:
        self.show(replace=True)

    def set_replace_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.replace_mode:
            return
        self.replace_mode = enabled
        if enabled:
            self._divider.pack(fill="x", pady=(7, 6))
            self.replace_row.pack(fill="x")
        else:
            self.replace_row.pack_forget()
            self._divider.pack_forget()

    def hide(self) -> None:
        if not self.visible:
            return
        self.visible = False
        self.place_forget()
        self._cancel_refresh()
        self._clear_tags()
        self.current = None
        editor = self._get_editor()
        if editor is not None:
            editor.focus_editor()
            editor.notify_cursor()

    def _on_escape(self, _event=None) -> str:
        self.hide()
        return "break"

    def _return_find(self, forward: bool) -> str:
        if forward:
            self.find_next()
        else:
            self.find_previous()
        return "break"

    def _return_replace(self) -> str:
        self.replace_current()
        return "break"

    def _selected_text(self, editor: "Editor") -> str:
        try:
            ranges = editor.text.tag_ranges("sel")
            if not ranges:
                return ""
            value = editor.text.get(ranges[0], ranges[1])
        except tk.TclError:
            return ""
        if not value or len(value) > 200 or "\n" in value or "\r" in value:
            return ""
        return value

    # -- options ------------------------------------------------------------
    def toggle_case(self) -> None:
        self.case_sensitive = not self.case_sensitive
        self._style_toggles()
        self.current = None
        self._refresh_matches()

    def toggle_whole_word(self) -> None:
        self.whole_word = not self.whole_word
        self._style_toggles()
        self.current = None
        self._refresh_matches()

    def _on_query_changed(self, *_args) -> None:
        if not self.visible:
            return
        self.current = None
        self._schedule_refresh()

    def _schedule_refresh(self, delay: int = 90) -> None:
        self._cancel_refresh()
        try:
            self._refresh_job = self.after(delay, self._refresh_matches)
        except tk.TclError:
            self._refresh_job = None

    def _cancel_refresh(self) -> None:
        if self._refresh_job is None:
            return
        try:
            self.after_cancel(self._refresh_job)
        except tk.TclError:
            pass
        self._refresh_job = None

    def on_editor_changed(self) -> None:
        """Called when the active document was edited or switched."""
        if not self.visible:
            return
        editor = self._get_editor()
        if editor is not self._tagged_editor:
            self._clear_tags()
            self._tagged_editor = editor
            self.current = None
            self._schedule_refresh(0)
            return
        self.current = None
        self._schedule_refresh(140)

    # -- search -------------------------------------------------------------
    def _find_all(self, editor: "Editor", query: str) -> list[tuple[str, str]]:
        text = editor.text
        found: list[tuple[str, str]] = []
        start = "1.0"
        try:
            while len(found) < self.MAX_MATCHES:
                self._count_var.set(0)
                index = text.search(
                    query,
                    start,
                    stopindex="end",
                    exact=True,
                    nocase=not self.case_sensitive,
                    count=self._count_var,
                )
                if not index:
                    break
                length = self._count_var.get()
                if length <= 0:
                    break
                end = text.index(f"{index}+{length}c")
                if not self.whole_word or self._is_whole_word(text, index, end):
                    found.append((index, end))
                start = end
        except tk.TclError:
            return found
        return found

    @staticmethod
    def _is_whole_word(text: tk.Text, start: str, end: str) -> bool:
        try:
            before = text.get(f"{start}-1c", start)
            after = text.get(end, f"{end}+1c")
        except tk.TclError:
            return False
        return not SearchBar._is_word_char(before[-1:]) and not SearchBar._is_word_char(
            after[:1]
        )

    @staticmethod
    def _is_word_char(char: str) -> bool:
        return bool(char) and (char.isalnum() or char == "_")

    def _refresh_matches(self) -> None:
        self._refresh_job = None
        editor = self._get_editor()
        query = self.find_var.get()
        if not self.visible or editor is None or not query:
            self.matches = []
            self.current = None
            self._clear_tags()
            self._update_count()
            return
        self._tagged_editor = editor
        self.matches = self._find_all(editor, query)
        if self.current not in self.matches:
            self.current = None
        self._apply_tags(editor, self.matches, self.current)
        self._update_count()

    def _navigate(self, direction: int, *, quiet: bool = False) -> bool:
        editor = self._get_editor()
        query = self.find_var.get()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return False
        if not query:
            if not self.visible:
                self.show()
            elif not quiet:
                self._set_status("请输入查找内容", "info")
            return False
        matches = self._find_all(editor, query)
        self.matches = matches
        self._tagged_editor = editor
        if not matches:
            self.current = None
            self._apply_tags(editor, [], None)
            self._update_count()
            if not quiet:
                self._set_status(f"未找到“{query}”", "warn")
            return False

        wrapped = False
        if self.current in matches:
            index = matches.index(self.current)
            target = (index + direction) % len(matches)
            wrapped = (direction > 0 and target == 0) or (
                direction < 0 and target == len(matches) - 1
            )
        else:
            insert = editor.text.index("insert")
            if direction > 0:
                candidates = [
                    index
                    for index, match in enumerate(matches)
                    if editor.text.compare(match[0], ">=", insert)
                ]
                target = candidates[0] if candidates else 0
                wrapped = not candidates
            else:
                candidates = [
                    index
                    for index, match in enumerate(matches)
                    if editor.text.compare(match[0], "<", insert)
                ]
                target = candidates[-1] if candidates else len(matches) - 1
                wrapped = not candidates

        self._select_match(editor, matches, target)
        if self.visible:
            self._apply_tags(editor, matches, self.current)
        self._update_count()
        if not quiet:
            if wrapped:
                self._set_status(
                    f"已循环查找 · 第 {target + 1} / {len(matches)} 处", "info"
                )
            else:
                self._set_status(
                    f"找到第 {target + 1} / {len(matches)} 处", "info"
                )
        return True

    def find_next(self) -> None:
        self._navigate(1)

    def find_previous(self) -> None:
        self._navigate(-1)

    def _select_match(
        self, editor: "Editor", matches: list[tuple[str, str]], index: int
    ) -> None:
        start, end = matches[index]
        self.current = (start, end)
        text = editor.text
        try:
            text.tag_remove("sel", "1.0", "end")
            text.tag_add("sel", start, end)
            text.mark_set("insert", end)
            text.see(start)
        except tk.TclError:
            return
        editor.notify_cursor()

    def _apply_tags(
        self,
        editor: "Editor",
        matches: list[tuple[str, str]],
        current: tuple[str, str] | None,
    ) -> None:
        self._ensure_tags(editor)
        text = editor.text
        try:
            text.tag_remove("find_match", "1.0", "end")
            text.tag_remove("find_current", "1.0", "end")
            for start, end in matches[: self.MAX_HIGHLIGHTS]:
                text.tag_add("find_match", start, end)
            if current is not None:
                text.tag_add("find_current", current[0], current[1])
            text.tag_raise("find_match")
            text.tag_raise("find_current")
        except tk.TclError:
            pass

    @staticmethod
    def _ensure_tags(editor: "Editor") -> None:
        try:
            editor.text.tag_configure(
                "find_match", background=Color.MATCH_BG, foreground=Color.MATCH_FG
            )
            editor.text.tag_configure(
                "find_current",
                background=Color.ACCENT,
                foreground=Color.TEXT_INVERSE,
            )
        except tk.TclError:
            pass

    def _clear_tags(self) -> None:
        editor = self._tagged_editor
        if editor is None or not self._widget_exists(editor):
            return
        try:
            editor.text.tag_remove("find_match", "1.0", "end")
            editor.text.tag_remove("find_current", "1.0", "end")
        except tk.TclError:
            pass

    def _update_count(self) -> None:
        query = self.find_var.get()
        if not query:
            self.count_label.configure(text="", fg=Color.TEXT_FAINT)
            return
        if not self.matches:
            self.count_label.configure(text="无结果", fg=Color.RED)
            return
        if self.current is not None:
            try:
                position = self.matches.index(self.current) + 1
            except ValueError:
                position = 0
            if position:
                self.count_label.configure(
                    text=f"{position} / {len(self.matches)}", fg=Color.ACCENT
                )
                return
        suffix = "+" if len(self.matches) >= self.MAX_MATCHES else ""
        self.count_label.configure(
            text=f"{len(self.matches)}{suffix} 处", fg=Color.TEXT_FAINT
        )

    # -- replace ------------------------------------------------------------
    def replace_current(self) -> None:
        editor = self._get_editor()
        query = self.find_var.get()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return
        if not query:
            self._set_status("请输入查找内容", "info")
            return
        if self.current is None:
            self._navigate(1)
            return
        start, end = self.current
        try:
            found = editor.text.get(start, end)
        except tk.TclError:
            return
        same = found == query
        if not same and not self.case_sensitive:
            same = found.casefold() == query.casefold()
        if not same:
            self.current = None
            self._navigate(1)
            return
        replacement = self.replace_var.get()
        self._edit_group(
            editor,
            lambda: self._replace_range(editor.text, start, end, replacement),
        )
        try:
            insert = editor.text.index(f"{start}+{len(replacement)}c")
            editor.text.mark_set("insert", insert)
        except tk.TclError:
            pass
        self.current = None
        self._refresh_matches()
        self._navigate(1, quiet=True)
        self._update_count()
        self._set_status("已替换 1 处", "ok")

    def replace_all(self) -> None:
        editor = self._get_editor()
        query = self.find_var.get()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return
        if not query:
            self._set_status("请输入查找内容", "info")
            return
        matches = self._find_all(editor, query)
        if not matches:
            self.matches = []
            self.current = None
            self._apply_tags(editor, [], None)
            self._update_count()
            self._set_status(f"未找到“{query}”", "warn")
            return
        replacement = self.replace_var.get()

        def apply() -> None:
            for start, end in reversed(matches):
                self._replace_range(editor.text, start, end, replacement)

        count = len(matches)
        self._edit_group(editor, apply)
        try:
            editor.text.tag_remove("sel", "1.0", "end")
            editor.text.mark_set("insert", matches[0][0])
        except tk.TclError:
            pass
        self.current = None
        self._refresh_matches()
        self._update_count()
        self._set_status(f"已替换 {count} 处", "ok")

    @staticmethod
    def _replace_range(text: tk.Text, start: str, end: str, replacement: str) -> None:
        text.delete(start, end)
        if replacement:
            text.insert(start, replacement)

    @staticmethod
    def _edit_group(editor: "Editor", action: Callable[[], None]) -> None:
        text = editor.text
        try:
            autoseparators = bool(int(text.cget("autoseparators")))
        except (tk.TclError, ValueError):
            autoseparators = True
        try:
            text.configure(autoseparators=False)
            text.edit_separator()
            action()
            text.edit_separator()
        finally:
            try:
                text.configure(autoseparators=autoseparators)
            except tk.TclError:
                pass

    def destroy(self) -> None:
        self._cancel_refresh()
        super().destroy()
