"""Square-cornered auxiliary dialogs."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from .theme import Color, font_ui
from .widgets import FlatButton


def center_window(window: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
    parent.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + max(0, (pw - width) // 2)
    y = py + max(0, (ph - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class _DialogBase(tk.Toplevel):
    """A modal, borderless dark dialog with its own square title bar."""

    def __init__(self, parent, title: str, width: int, height: int) -> None:
        super().__init__(parent)
        self.parent = parent
        self._title = title
        self.configure(
            bg=Color.BORDER_BRIGHT,
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        self.overrideredirect(True)
        self.resizable(False, False)
        self.transient(parent)
        self._width = width
        self._height = height
        self._drag_origin: tuple[int, int] | None = None
        self.bind("<Escape>", lambda _e: self.close())

        title_bar = tk.Frame(self, bg=Color.CHROME_ALT, height=32)
        title_bar.pack(side="top", fill="x")
        title_bar.pack_propagate(False)
        self._title_bar = title_bar
        tk.Frame(title_bar, bg=Color.BORDER_SOFT, height=1).pack(side="bottom", fill="x")
        mark = tk.Canvas(
            title_bar, width=9, height=9, bg=Color.CHROME_ALT, highlightthickness=0
        )
        mark.pack(side="left", padx=(12, 8))
        mark.create_rectangle(0, 0, 8, 8, fill=Color.ACCENT, outline="")
        title_label = tk.Label(
            title_bar,
            text=f"PASCAL BOX   /   {title}",
            bg=Color.CHROME_ALT,
            fg=Color.TEXT_DIM,
            font=("Consolas", 8),
            anchor="w",
        )
        title_label.pack(side="left", fill="y")
        close_button = FlatButton(
            title_bar,
            text="×",
            kind="ghost",
            command=self.close,
            padx=10,
            pady=0,
            border=False,
            font=("Segoe UI", 12),
        )
        close_button.configure(
            bg=Color.CHROME_ALT,
            activebackground=Color.UNMATCHED_BG,
            highlightbackground=Color.CHROME_ALT,
        )
        close_button.pack(side="right", fill="y")
        for widget in (title_bar, title_label, mark):
            widget.bind("<Button-1>", self._begin_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
        self.after_idle(self._place)

    def _begin_drag(self, event) -> None:
        self._drag_origin = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag(self, event) -> None:
        if self._drag_origin is None:
            return
        x = event.x_root - self._drag_origin[0]
        y = event.y_root - self._drag_origin[1]
        self.geometry(f"+{x}+{y}")

    def _end_drag(self, _event=None) -> None:
        self._drag_origin = None

    def _place(self) -> None:
        self.update_idletasks()
        center_window(self, self.parent, self._width, self._height)
        self.lift()
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.grab_set()
        try:
            self.focus_force()
        except tk.TclError:
            self.focus_set()

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class IndentDialog(_DialogBase):
    def __init__(
        self,
        parent,
        tab_width: int,
        use_spaces: bool,
        on_apply: Callable[[int, bool], None],
    ) -> None:
        super().__init__(parent, "缩进设置", 500, 462)
        self._tab_width = max(1, min(8, int(tab_width)))
        self._use_spaces = bool(use_spaces)
        self._on_apply = on_apply

        accent = tk.Frame(self, bg=Color.ACCENT, height=3)
        accent.pack(fill="x")
        header = tk.Frame(self, bg=Color.CHROME, height=63)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="缩进设置",
            bg=Color.CHROME,
            fg=Color.TEXT,
            font=font_ui(13, "bold"),
            anchor="w",
        ).pack(side="left", padx=22)
        tk.Label(
            header,
            text="仅影响编辑与自动缩进，不改变已有文件内容",
            bg=Color.CHROME,
            fg=Color.TEXT_FAINT,
            font=font_ui(8),
            anchor="e",
        ).pack(side="right", padx=22)

        body = tk.Frame(self, bg=Color.BG, padx=24, pady=20)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="制表符宽度",
            bg=Color.BG,
            fg=Color.TEXT,
            font=font_ui(10, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text="设置按 Tab 键时使用的宽度，以及文件中 Tab 字符的显示宽度。",
            bg=Color.BG,
            fg=Color.TEXT_DIM,
            font=font_ui(8),
            anchor="w",
        ).pack(fill="x", pady=(4, 10))

        self._width_row = tk.Frame(body, bg=Color.BG)
        self._width_row.pack(fill="x")
        self._build_width_buttons()

        spacer = tk.Frame(body, bg=Color.BG, height=20)
        spacer.pack(fill="x")
        tk.Label(
            body,
            text="Tab 键插入",
            bg=Color.BG,
            fg=Color.TEXT,
            font=font_ui(10, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text="空格方式能保证源代码在任何编辑器中对齐一致。",
            bg=Color.BG,
            fg=Color.TEXT_DIM,
            font=font_ui(8),
            anchor="w",
        ).pack(fill="x", pady=(4, 10))
        self._mode_row = tk.Frame(body, bg=Color.BG)
        self._mode_row.pack(fill="x")
        self._build_mode_buttons()

        footer = tk.Frame(self, bg=Color.CHROME, height=60)
        footer.pack(fill="x", side="bottom", before=body)
        footer.pack_propagate(False)
        tk.Frame(footer, bg=Color.BORDER_SOFT, height=1).pack(fill="x", side="top")
        apply_button = FlatButton(
            footer,
            text="应用",
            kind="primary",
            command=self._apply,
            padx=22,
            pady=6,
        )
        apply_button.pack(side="right", padx=(0, 18), pady=11)
        cancel_button = FlatButton(
            footer,
            text="取消",
            kind="secondary",
            command=self.close,
            padx=20,
            pady=6,
        )
        cancel_button.pack(side="right", padx=(0, 8), pady=11)

    def _build_width_buttons(self) -> None:
        for child in self._width_row.winfo_children():
            child.destroy()
        for width in range(1, 9):
            selected = width == self._tab_width
            button = FlatButton(
                self._width_row,
                text=str(width),
                kind="primary" if selected else "secondary",
                command=lambda value=width: self._set_width(value),
                font=font_ui(10, "bold" if selected else "normal"),
                padx=0,
                pady=5,
                width=3,
            )
            button.pack(side="left", padx=(0, 7))

    def _build_mode_buttons(self) -> None:
        for child in self._mode_row.winfo_children():
            child.destroy()
        for label, value in (("插入空格", True), ("插入制表符", False)):
            selected = value == self._use_spaces
            button = FlatButton(
                self._mode_row,
                text=label,
                kind="primary" if selected else "secondary",
                command=lambda selected_value=value: self._set_mode(selected_value),
                font=font_ui(9, "bold" if selected else "normal"),
                padx=20,
                pady=6,
            )
            button.pack(side="left", padx=(0, 8))

    def _set_width(self, width: int) -> None:
        self._tab_width = width
        self._build_width_buttons()

    def _set_mode(self, use_spaces: bool) -> None:
        self._use_spaces = use_spaces
        self._build_mode_buttons()

    def _apply(self) -> None:
        self._on_apply(self._tab_width, self._use_spaces)
        self.close()


class ShortcutsDialog(_DialogBase):
    GROUPS = [
        (
            "文件",
            [
                ("Ctrl+N", "新建文件"),
                ("Ctrl+O", "打开文件"),
                ("Ctrl+S", "保存"),
                ("Ctrl+Shift+S", "另存为"),
                ("Ctrl+W", "关闭当前标签"),
            ],
        ),
        (
            "编辑",
            [
                ("Ctrl+Z / Ctrl+Y", "撤销 / 重做"),
                ("Tab / Shift+Tab", "增加 / 减少缩进"),
                ("(  [", "自动补全括号"),
                ("Ctrl+A", "全选"),
                ("Ctrl+F", "查找"),
                ("Ctrl+H", "查找并替换"),
                ("F3 / Shift+F3", "查找下一个 / 上一个"),
                ("Esc", "关闭查找栏"),
            ],
        ),
        (
            "构建与运行",
            [
                ("F6", "编译当前文件"),
                ("F7", "运行已编译程序"),
                ("F5", "编译并运行"),
                ("Ctrl+F2", "停止正在运行的程序"),
            ],
        ),
        (
            "查看",
            [
                ("Ctrl+Tab", "切换到下一个标签"),
                ("Ctrl+Shift+Tab", "切换到上一个标签"),
                ("Ctrl+`", "显示 / 隐藏输出面板"),
                ("Ctrl+= / Ctrl+-", "调整编辑器字号"),
            ],
        ),
    ]

    def __init__(self, parent) -> None:
        super().__init__(parent, "快捷键", 650, 632)
        accent = tk.Frame(self, bg=Color.ACCENT, height=3)
        accent.pack(fill="x")
        header = tk.Frame(self, bg=Color.CHROME, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="快捷键",
            bg=Color.CHROME,
            fg=Color.TEXT,
            font=font_ui(13, "bold"),
            anchor="w",
        ).pack(side="left", padx=22)
        tk.Label(
            header,
            text="PASCAL BOX",
            bg=Color.CHROME,
            fg=Color.TEXT_FAINT,
            font=font_ui(8),
            anchor="e",
        ).pack(side="right", padx=22)

        body = tk.Frame(self, bg=Color.BG, padx=22, pady=16)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=Color.BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=Color.BG)
        right.pack(side="left", fill="both", expand=True, padx=(24, 0))

        for column, groups in ((left, self.GROUPS[:2]), (right, self.GROUPS[2:])):
            for title, rows in groups:
                tk.Label(
                    column,
                    text=title.upper(),
                    bg=Color.BG,
                    fg=Color.ACCENT,
                    font=font_ui(8, "bold"),
                    anchor="w",
                ).pack(fill="x", pady=(4, 7))
                for key, description in rows:
                    row = tk.Frame(column, bg=Color.BG)
                    row.pack(fill="x", pady=3)
                    badge = tk.Frame(row, bg=Color.BORDER, padx=1, pady=1)
                    badge.pack(side="left")
                    tk.Label(
                        badge,
                        text=key,
                        bg=Color.BTN_BG,
                        fg=Color.ACCENT,
                        font=("Consolas", 8),
                        padx=6,
                        pady=2,
                    ).pack()
                    tk.Label(
                        row,
                        text=description,
                        bg=Color.BG,
                        fg=Color.TEXT_DIM,
                        font=font_ui(8),
                        anchor="w",
                    ).pack(side="left", padx=(10, 0))
                tk.Frame(column, bg=Color.BG, height=10).pack(fill="x")

        footer = tk.Frame(self, bg=Color.CHROME, height=54)
        footer.pack(fill="x", side="bottom", before=body)
        footer.pack_propagate(False)
        tk.Frame(footer, bg=Color.BORDER_SOFT, height=1).pack(fill="x", side="top")
        FlatButton(
            footer,
            text="关闭",
            kind="secondary",
            command=self.close,
            padx=24,
            pady=5,
        ).pack(side="right", padx=18, pady=9)


class AboutDialog(_DialogBase):
    def __init__(self, parent, fpc_version: str, fpc_path: str) -> None:
        super().__init__(parent, "关于 Pascal Box", 480, 382)
        tk.Frame(self, bg=Color.ACCENT, height=3).pack(fill="x")
        body = tk.Frame(self, bg=Color.BG, padx=28, pady=26)
        body.pack(fill="both", expand=True)

        logo_row = tk.Frame(body, bg=Color.BG)
        logo_row.pack(fill="x")
        logo = tk.Canvas(logo_row, width=46, height=46, bg=Color.BG, highlightthickness=0)
        logo.pack(side="left")
        logo.create_rectangle(0, 0, 45, 45, fill=Color.ACCENT, outline="")
        logo.create_text(23, 22, text="P", fill=Color.TEXT_INVERSE,
                         font=("Bahnschrift SemiBold", 22))
        title_block = tk.Frame(logo_row, bg=Color.BG)
        title_block.pack(side="left", padx=16)
        tk.Label(
            title_block,
            text="PASCAL BOX",
            bg=Color.BG,
            fg=Color.TEXT,
            font=("Bahnschrift SemiBold", 17),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="面向 Object Pascal 的轻量集成开发环境",
            bg=Color.BG,
            fg=Color.TEXT_DIM,
            font=font_ui(9),
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        tk.Frame(body, bg=Color.BORDER_SOFT, height=1).pack(fill="x", pady=(22, 16))
        self._info_row(body, "版 本", "1.0.0")
        self._info_row(body, "编 译 器", f"Free Pascal {fpc_version or '未检测到'}")
        self._info_row(body, "编译器路径", fpc_path or "未找到 fpc")
        tk.Label(
            body,
            text="文件读写 · 多标签编辑 · 语法高亮 · 括号匹配 · FPC 一键构建",
            bg=Color.BG,
            fg=Color.TEXT_FAINT,
            font=font_ui(8),
            anchor="w",
        ).pack(fill="x", pady=(18, 0))

        footer = tk.Frame(self, bg=Color.CHROME, height=52)
        footer.pack(fill="x", side="bottom", before=body)
        footer.pack_propagate(False)
        tk.Frame(footer, bg=Color.BORDER_SOFT, height=1).pack(fill="x", side="top")
        FlatButton(
            footer,
            text="关闭",
            kind="primary",
            command=self.close,
            padx=24,
            pady=5,
        ).pack(side="right", padx=20, pady=8)

    def _info_row(self, parent, label: str, value: str) -> None:
        row = tk.Frame(parent, bg=Color.BG)
        row.pack(fill="x", pady=2)
        tk.Label(
            row,
            text=label,
            bg=Color.BG,
            fg=Color.TEXT_FAINT,
            font=font_ui(8),
            width=12,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            row,
            text=value,
            bg=Color.BG,
            fg=Color.TEXT_DIM,
            font=("Consolas", 8),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
