"""Pascal Box application shell."""

from __future__ import annotations

import ctypes
import os
import queue
import re
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

from .dialogs import AboutDialog, IndentDialog, ShortcutsDialog
from .editor import Editor, SourceText, read_source_file, write_source_file
from .runner import CompileResult, FpcToolchain, ProgramRunner
from .searchbar import SearchBar
from .settings import Settings
from .sharp_menu import SharpMenu
from .theme import Color, Font, apply_theme, font_mono, font_ui, normalize_theme
from .widgets import FlatButton, FlatScrollbar, SectionTab, TabBar


STARTER = """program Hello;

begin
  writeln('Hello!');
end.
"""

COMPILE_ERROR_RE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+)(?:,(?P<col>\d+))?\)\s+"
    r"(?P<severity>Fatal|Error|Warning|Note|Hint):\s*(?P<message>.*)$"
)

ERROR_POSITION_RE = re.compile(
    r"^.+?\(\d+(?:,\d+)?\)\s+(?:Error|Fatal):", re.IGNORECASE | re.MULTILINE
)
WARNING_POSITION_RE = re.compile(
    r"^.+?\(\d+(?:,\d+)?\)\s+Warning:", re.IGNORECASE | re.MULTILINE
)
ERROR_SUMMARY_RE = re.compile(r"There were (\d+) errors?", re.IGNORECASE)


class PascalBox(tk.Tk):
    def __init__(self, initial_files: list[str] | None = None) -> None:
        super().__init__()
        self._closing = False
        self.settings = Settings()
        self.theme = normalize_theme(str(self.settings.get("theme", "dark")))
        apply_theme(self.theme)
        self.toolchain = FpcToolchain()
        self._apply_font_fallbacks()

        self.editors: list[Editor] = []
        self.active_index = -1
        self.untitled_counter = 0
        self._events: queue.Queue = queue.Queue()
        self._compile_busy = False
        self._compile_token = 0
        self._run_token = 0
        self._stop_requested = False
        self.active_runner: ProgramRunner | None = None
        self._last_compile_dir = Path.cwd()
        self._last_build: CompileResult | None = None
        self._output_visible = bool(self.settings.get("output_visible", True))
        self._closed_after_prompt = False
        self._indent_dialog: IndentDialog | None = None
        self._shortcuts_dialog: ShortcutsDialog | None = None
        self._about_dialog: AboutDialog | None = None
        self._link_seq = 0
        self._drag_split_origin = 0
        self._drag_split_height = 0
        self._menu_buttons: list[FlatButton] = []
        self._poll_job: str | None = None

        self._configure_root()
        self._make_icon()
        self._build_ui()
        self._build_menu()
        self._bind_global_shortcuts()
        self._apply_setting_widgets()
        self._start_initial(initial_files)
        if self.toolchain.available:
            version = f" · FPC {self.toolchain.version}" if self.toolchain.version else ""
            self._set_status(f"就绪{version}", "ready")
        else:
            self._set_status("未找到 FPC，请在 PATH 中安装或配置 PASCAL_BOX_FPC", "warn")
        self.after(40, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._apply_native_window_style)

    # ------------------------------------------------------------------
    # Window and fonts
    # ------------------------------------------------------------------
    def _configure_root(self) -> None:
        self.title("Pascal Box")
        self.configure(bg=Color.BG)
        self.minsize(980, 620)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = max(980, min(1380, screen_w - 60))
        height = max(620, min(850, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 12)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def _apply_font_fallbacks(self) -> None:
        families = set(tkfont.families(self))
        if Font.UI not in families:
            Font.UI = "Segoe UI" if "Segoe UI" in families else "TkDefaultFont"
        if Font.MONO not in families:
            Font.MONO = Font.MONO_FALLBACK if Font.MONO_FALLBACK in families else "Courier New"
        if Font.BRAND not in families:
            Font.BRAND = Font.UI

    def _make_icon(self) -> None:
        icon = tk.PhotoImage(width=32, height=32)
        icon.put(Color.ACCENT, to=(0, 0, 32, 32))
        # A strictly rectangular P, matching the application chrome.
        icon.put(Color.TEXT_INVERSE, to=(9, 6, 13, 26))
        icon.put(Color.TEXT_INVERSE, to=(9, 6, 23, 10))
        icon.put(Color.TEXT_INVERSE, to=(20, 8, 24, 17))
        icon.put(Color.TEXT_INVERSE, to=(9, 14, 22, 18))
        try:
            self.iconphoto(True, icon)
        except tk.TclError:
            pass
        self._icon = icon

    def _apply_native_window_style(self) -> None:
        """Ask Windows for a dark, square window frame where supported."""
        if os.name != "nt":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            value = ctypes.c_int(1 if getattr(self, "theme", "dark") == "dark" else 0)
            # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), 4)
            # DWMWA_WINDOW_CORNER_PREFERENCE / DWMWCP_DONOTROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), 4)
            # Caption, border and text colours (Windows 11).  COLORREF is BGR.
            caption = self._colorref(Color.CHROME)
            border = self._colorref(Color.BORDER)
            text_color = self._colorref(Color.TEXT)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(ctypes.c_int(caption)), 4
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(ctypes.c_int(border)), 4
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(ctypes.c_int(text_color)), 4
            )
        except Exception:
            pass

    @staticmethod
    def _colorref(hex_color: str) -> int:
        value = hex_color.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return r | (g << 8) | (b << 16)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._build_header()
        self.tabbar = TabBar(
            self,
            on_select=self._switch_tab,
            on_close=self._close_tab,
            on_new=lambda: self.new_file(),
            on_reorder=self._reorder_tab,
        )
        self.tabbar.grid(row=1, column=0, sticky="ew")
        self.editor_host = tk.Frame(self, bg=Color.EDITOR_BG, bd=0, highlightthickness=0)
        self.editor_host.grid(row=2, column=0, sticky="nsew")
        self._build_splitter()
        self._build_output_panel()
        self._build_statusbar()
        self.search_bar = SearchBar(
            self.editor_host,
            get_editor=self.current_editor,
            set_status=self._set_status,
        )
        if not self._output_visible:
            self.output_panel.grid_remove()
            self.splitter.grid_remove()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=Color.CHROME_ALT, height=28, bd=0, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)
        self.header = header
        tk.Frame(header, bg=Color.BORDER_SOFT, height=1).pack(side="bottom", fill="x")
        self.menu_strip = header
        self.menu_buttons_host = tk.Frame(header, bg=Color.CHROME_ALT)
        self.menu_buttons_host.pack(side="left", fill="y", padx=(8, 0))

    def _build_splitter(self) -> None:
        self.splitter = tk.Canvas(
            self,
            height=6,
            bg=Color.CHROME_ALT,
            highlightthickness=0,
            bd=0,
            cursor="sb_v_double_arrow",
        )
        self.splitter.grid(row=3, column=0, sticky="ew")
        self.splitter.bind("<Configure>", self._draw_splitter)
        self.splitter.bind("<Enter>", lambda _e: self._draw_splitter(hover=True))
        self.splitter.bind("<Leave>", lambda _e: self._draw_splitter(hover=False))
        self.splitter.bind("<Button-1>", self._split_press)
        self.splitter.bind("<B1-Motion>", self._split_drag)
        self.splitter.bind("<ButtonRelease-1>", self._split_release)
        self._splitter_hover = False

    def _draw_splitter(self, _event=None, hover: bool | None = None) -> None:
        if hover is not None:
            self._splitter_hover = hover
        c = self.splitter
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        c.create_rectangle(0, 0, w, h, fill=Color.CHROME_ALT, outline="")
        color = Color.ACCENT if self._splitter_hover else Color.BORDER
        c.create_line(0, h // 2, w, h // 2, fill=color)
        if not self._output_visible:
            return
        # A small square grip in the centre.
        cx = w // 2
        c.create_rectangle(cx - 13, h // 2 - 1, cx - 9, h // 2 + 1, fill=Color.TEXT_FAINT, outline="")
        c.create_rectangle(cx - 3, h // 2 - 1, cx + 1, h // 2 + 1, fill=Color.TEXT_FAINT, outline="")
        c.create_rectangle(cx + 7, h // 2 - 1, cx + 11, h // 2 + 1, fill=Color.TEXT_FAINT, outline="")

    def _split_press(self, event) -> None:
        self._drag_split_origin = event.y_root
        self._drag_split_height = self.output_panel.winfo_height()

    def _split_drag(self, event) -> None:
        delta = self._drag_split_origin - event.y_root
        height = self._drag_split_height + delta
        max_height = max(120, self.winfo_height() - 260)
        height = max(110, min(max_height, height))
        self.output_panel.configure(height=height)
        self.settings.set("output_height", int(height), save=False)

    def _split_release(self, _event=None) -> None:
        self.settings.save()

    def _build_output_panel(self) -> None:
        height = int(self.settings.get("output_height", 220))
        panel = tk.Frame(self, bg=Color.CHROME_ALT, height=height, bd=0, highlightthickness=0)
        panel.grid(row=4, column=0, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        self.output_panel = panel

        header = tk.Frame(panel, bg=Color.CHROME, height=35, bd=0, highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)
        tk.Frame(header, bg=Color.BORDER_SOFT, height=1).pack(side="bottom", fill="x")
        tabs = tk.Frame(header, bg=Color.CHROME)
        tabs.pack(side="left", fill="y", padx=(6, 0))
        self.compile_section_tab = SectionTab(
            tabs, "编译输出", lambda: None, bg=Color.CHROME
        )
        self.compile_section_tab.pack(side="left", fill="y")
        self.compile_section_tab.set_active(True)

        actions = tk.Frame(header, bg=Color.CHROME)
        actions.pack(side="right", fill="y", padx=(0, 8))
        clear_button = FlatButton(
            actions,
            text="清空",
            kind="ghost",
            command=self.clear_output,
            padx=9,
            pady=1,
            border=False,
        )
        clear_button.pack(side="right", pady=7, padx=2)
        collapse_button = FlatButton(
            actions,
            text="收起",
            kind="ghost",
            command=self.toggle_output,
            padx=9,
            pady=1,
            border=False,
        )
        collapse_button.pack(side="right", pady=7, padx=2)

        content = tk.Frame(panel, bg=Color.PANEL_BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self.output_content = content

        self.compile_frame, self.compile_text = self._make_output_pane(content)

        # Short hint, removed when the first real output arrives.
        self._insert_output_text(
            self.compile_text,
            "编译输出会显示在这里。按 F6 编译，F5 编译并在终端中运行。\n",
            "muted",
        )

    def _make_output_pane(self, parent) -> tuple[tk.Frame, tk.Text]:
        frame = tk.Frame(parent, bg=Color.PANEL_BG)
        frame.grid(row=0, column=0, sticky="nsew")
        text = tk.Text(
            frame,
            wrap="word",
            bg=Color.PANEL_BG,
            fg=Color.TEXT,
            insertbackground=Color.CARET,
            selectbackground=Color.SELECTION,
            selectforeground=Color.TEXT,
            highlightthickness=0,
            bd=0,
            relief="flat",
            padx=14,
            pady=9,
            font=font_mono(9),
            state="disabled",
            cursor="arrow",
            spacing1=1,
            spacing3=1,
        )
        scroll = FlatScrollbar(frame, command=text.yview, bg=Color.PANEL_BG)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.configure(yscrollcommand=scroll.set)
        text.tag_configure("meta", foreground=Color.ACCENT)
        text.tag_configure("ok", foreground=Color.GREEN)
        text.tag_configure("err", foreground=Color.RED)
        text.tag_configure("warn", foreground=Color.YELLOW)
        text.tag_configure("muted", foreground=Color.TEXT_FAINT)
        text.tag_configure("stdout", foreground=Color.TEXT)
        text.tag_configure("input", foreground=Color.BLUE)
        text.tag_configure("header", foreground=Color.TEXT_DIM, font=font_mono(9, "bold"))
        text.bind("<Control-c>", self._copy_output)
        return frame, text

    def _insert_output_text(self, widget: tk.Text, text: str, tag: str | None = None) -> None:
        try:
            widget.configure(state="normal")
            if tag:
                widget.insert("end", text, tag)
            else:
                widget.insert("end", text)
            widget.configure(state="disabled")
            widget.see("end-1c")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_statusbar(self) -> None:
        bar = tk.Frame(self, bg=Color.CHROME, height=27, bd=0, highlightthickness=0)
        bar.grid(row=5, column=0, sticky="ew")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=Color.BORDER_SOFT, height=1).pack(side="top", fill="x")
        left = tk.Frame(bar, bg=Color.CHROME)
        left.pack(side="left", fill="y", padx=(13, 0))
        self.status_dot = tk.Canvas(
            left, width=8, height=8, bg=Color.CHROME, highlightthickness=0
        )
        self.status_dot.pack(side="left", pady=9, padx=(0, 8))
        self._draw_status_dot(Color.GREEN)
        self.status_label = tk.Label(
            left,
            text="就绪",
            bg=Color.CHROME,
            fg=Color.TEXT_DIM,
            font=font_ui(8),
            anchor="w",
        )
        self.status_label.pack(side="left")

        right = tk.Frame(bar, bg=Color.CHROME)
        right.pack(side="right", fill="y", padx=(0, 14))
        self.tab_status = self._status_chip(right, "Tab 4 · 空格")
        self.eol_status = self._status_chip(right, "CRLF")
        self.encoding_status = self._status_chip(right, "UTF-8")
        self.lines_status = self._status_chip(right, "1 行")
        self.cursor_status = self._status_chip(right, "行 1，列 1")
        for chip in (
            self.tab_status,
            self.eol_status,
            self.encoding_status,
            self.lines_status,
            self.cursor_status,
        ):
            chip.pack(side="right", padx=(0, 10))

    def _status_chip(self, parent, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=Color.CHROME,
            fg=Color.TEXT_FAINT,
            font=("Consolas", 8),
            pady=5,
        )

    def _draw_status_dot(self, color: str) -> None:
        self.status_dot.delete("all")
        self.status_dot.create_rectangle(0, 0, 7, 7, fill=color, outline="")

    def _set_status(self, text: str, level: str = "info") -> None:
        colors = {
            "ready": Color.GREEN,
            "info": Color.TEXT_DIM,
            "working": Color.ACCENT,
            "ok": Color.GREEN,
            "error": Color.RED,
            "warn": Color.YELLOW,
        }
        self.status_label.configure(text=text, fg=colors.get(level, Color.TEXT_DIM))
        self._draw_status_dot(colors.get(level, Color.TEXT_DIM))

    def _refresh_status(self) -> None:
        editor = self.current_editor()
        if editor is None:
            return
        try:
            line = int(editor.text.index("insert").split(".")[0])
            col = int(editor.text.index("insert").split(".")[1]) + 1
        except (tk.TclError, ValueError):
            line, col = 1, 1
        self.cursor_status.configure(text=f"行 {line}，列 {col}")
        self.lines_status.configure(text=f"{editor.line_count()} 行")
        self.encoding_status.configure(text=editor.encoding_label)
        self.eol_status.configure(text="CRLF" if editor.newline == "\r\n" else "LF")
        mode = "空格" if editor.use_spaces else "Tab"
        self.tab_status.configure(text=f"Tab {editor.tab_width} · {mode}")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        file_menu = self._make_popup_menu()
        file_menu.add_command(label="新建", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="打开…", accelerator="Ctrl+O", command=self._open_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="保存", accelerator="Ctrl+S", command=self.save_current)
        file_menu.add_command(
            label="另存为…", accelerator="Ctrl+Shift+S", command=self.save_current_as
        )
        file_menu.add_command(label="全部保存", command=self.save_all)
        file_menu.add_separator()
        file_menu.add_command(label="关闭标签", accelerator="Ctrl+W", command=self.close_current)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)

        edit_menu = self._make_popup_menu()
        edit_menu.add_command(
            label="撤销", accelerator="Ctrl+Z", command=lambda: self._edit_action("Undo")
        )
        edit_menu.add_command(
            label="重做", accelerator="Ctrl+Y", command=lambda: self._edit_action("Redo")
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="剪切", accelerator="Ctrl+X", command=lambda: self._edit_action("Cut")
        )
        edit_menu.add_command(
            label="复制", accelerator="Ctrl+C", command=lambda: self._edit_action("Copy")
        )
        edit_menu.add_command(
            label="粘贴", accelerator="Ctrl+V", command=lambda: self._edit_action("Paste")
        )
        edit_menu.add_command(label="全选", accelerator="Ctrl+A", command=self.select_all)
        edit_menu.add_separator()
        edit_menu.add_command(
            label="查找…", accelerator="Ctrl+F", command=self.show_find
        )
        edit_menu.add_command(
            label="替换…", accelerator="Ctrl+H", command=self.show_replace
        )
        edit_menu.add_command(label="查找下一个", accelerator="F3", command=self._find_next)
        edit_menu.add_command(
            label="查找上一个", accelerator="Shift+F3", command=self._find_previous
        )

        view_menu = self._make_popup_menu()
        view_menu.add_command(
            label="增大字号", accelerator="Ctrl+=", command=lambda: self.zoom_editor(1)
        )
        view_menu.add_command(
            label="减小字号", accelerator="Ctrl+-", command=lambda: self.zoom_editor(-1)
        )
        view_menu.add_command(label="重置字号", accelerator="Ctrl+0", command=self.reset_zoom)
        view_menu.add_separator()
        view_menu.add_command(
            label="切换亮色 / 暗色主题",
            accelerator="Ctrl+T",
            command=self.toggle_theme,
        )
        view_menu.add_command(label="缩进设置…", command=self.open_indent_dialog)
        view_menu.add_command(
            label="显示 / 隐藏输出面板", accelerator="Ctrl+`", command=self.toggle_output
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="下一个标签", accelerator="Ctrl+Tab", command=lambda: self.cycle_tab(1)
        )
        view_menu.add_command(
            label="上一个标签",
            accelerator="Ctrl+Shift+Tab",
            command=lambda: self.cycle_tab(-1),
        )

        run_menu = self._make_popup_menu()
        run_menu.add_command(
            label="编译", accelerator="F6", command=lambda: self.compile_current(False)
        )
        run_menu.add_command(label="运行", accelerator="F7", command=self.run_current)
        run_menu.add_command(
            label="编译并运行", accelerator="F5", command=lambda: self.compile_current(True)
        )
        run_menu.add_separator()
        run_menu.add_command(
            label="停止程序", accelerator="Ctrl+F2", command=self.stop_program
        )

        help_menu = self._make_popup_menu()
        help_menu.add_command(label="快捷键", command=self.open_shortcuts)
        help_menu.add_command(label="关于 Pascal Box", command=self.open_about)

        self.menus: dict[str, SharpMenu] = {
            "文件": file_menu,
            "编辑": edit_menu,
            "查看": view_menu,
            "运行": run_menu,
            "帮助": help_menu,
        }
        for label, menu in self.menus.items():
            self._add_menu_button(label, menu)

    def _make_popup_menu(self) -> SharpMenu:
        return SharpMenu(self)

    def _add_menu_button(self, label: str, menu: SharpMenu) -> None:
        palette = {
            "bg": Color.CHROME_ALT,
            "fg": Color.TEXT_DIM,
            "hover": Color.BTN_HOVER,
            "active": Color.BTN_PRESSED,
            "border": Color.CHROME_ALT,
        }
        button = FlatButton(
            self.menu_buttons_host,
            text=label,
            kind="flat",
            palette=palette,
            padx=10,
            pady=2,
            border=False,
            font=font_ui(9),
        )
        button.configure(command=lambda m=menu, b=button: self._post_menu(m, b))
        button.pack(side="left", padx=1, pady=2)
        self._menu_buttons.append(button)

    def _post_menu(self, menu: SharpMenu, button: FlatButton) -> None:
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            menu.post(x, y)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------
    def _shortcut_pairs(self) -> list[tuple[str, Callable]]:
        return [
            ("<Control-n>", self.new_file),
            ("<Control-o>", self._open_dialog),
            ("<Control-s>", self.save_current),
            ("<Control-Shift-S>", self.save_current_as),
            ("<Control-Shift-s>", self.save_current_as),
            ("<Control-w>", self.close_current),
            ("<Control-Tab>", lambda: self.cycle_tab(1)),
            ("<Control-Shift-Tab>", lambda: self.cycle_tab(-1)),
            ("<Control-ISO_Left_Tab>", lambda: self.cycle_tab(-1)),
            ("<Control-F2>", self.stop_program),
            ("<Control-grave>", self.toggle_output),
            ("<Control-t>", self.toggle_theme),
            ("<Control-equal>", lambda: self.zoom_editor(1)),
            ("<Control-plus>", lambda: self.zoom_editor(1)),
            ("<Control-minus>", lambda: self.zoom_editor(-1)),
            ("<Control-0>", self.reset_zoom),
            ("<Control-f>", self.show_find),
            ("<Control-F>", self.show_find),
            ("<Control-h>", self.show_replace),
            ("<Control-H>", self.show_replace),
            ("<F3>", self._find_next),
            ("<Shift-F3>", self._find_previous),
            ("<F5>", lambda: self.compile_current(True)),
            ("<F6>", lambda: self.compile_current(False)),
            ("<F7>", self.run_current),
        ]

    def _make_shortcut_handler(self, action: Callable):
        def handler(_event=None):
            action()
            return "break"

        return handler

    def _bind_global_shortcuts(self) -> None:
        for sequence, action in self._shortcut_pairs():
            try:
                self.bind(sequence, self._make_shortcut_handler(action))
            except tk.TclError:
                pass

    def _bind_editor_shortcuts(self, widget: tk.Widget) -> None:
        for sequence, action in self._shortcut_pairs():
            try:
                widget.bind(sequence, self._make_shortcut_handler(action), add="+")
            except tk.TclError:
                pass
        widget.bind("<Control-a>", self._select_all_shortcut)
        widget.bind("<Control-A>", self._select_all_shortcut)
        if isinstance(widget, tk.Text):
            widget.bind("<Control-z>", self._undo_shortcut)
            widget.bind("<Control-Z>", self._undo_shortcut)
            widget.bind("<Control-y>", self._redo_shortcut)
            widget.bind("<Control-Y>", self._redo_shortcut)

    def _select_all_shortcut(self, _event=None) -> str:
        widget = self.focus_get()
        if isinstance(widget, tk.Entry):
            widget.selection_range(0, "end")
        elif isinstance(widget, tk.Text):
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")
        return "break"

    def _undo_shortcut(self, event=None) -> str:
        event.widget.event_generate("<<Undo>>")
        return "break"

    def _redo_shortcut(self, event=None) -> str:
        event.widget.event_generate("<<Redo>>")
        return "break"

    def _edit_action(self, action: str) -> None:
        widget = self.focus_get()
        if not isinstance(widget, (tk.Text, tk.Entry)):
            editor = self.current_editor()
            widget = editor.text if editor is not None else None
        if widget is None:
            return
        try:
            widget.event_generate(f"<<{action}>>")
        except tk.TclError:
            pass

    def select_all(self) -> None:
        widget = self.focus_get()
        if not isinstance(widget, (tk.Text, tk.Entry)):
            editor = self.current_editor()
            if editor is not None:
                editor.text.tag_remove("sel", "1.0", "end")
                editor.text.tag_add("sel", "1.0", "end-1c")
                editor.focus_editor()
            return
        if isinstance(widget, tk.Entry):
            widget.selection_range(0, "end")
        elif isinstance(widget, tk.Text):
            widget.tag_remove("sel", "1.0", "end")
            widget.tag_add("sel", "1.0", "end-1c")

    def _copy_output(self, event=None) -> str:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            ranges = widget.tag_ranges("sel")
            if ranges:
                self.clipboard_clear()
                self.clipboard_append(widget.get(ranges[0], ranges[1]))
        return "break"

    # ------------------------------------------------------------------
    # Find and replace
    # ------------------------------------------------------------------
    def show_find(self) -> None:
        self.search_bar.show_find()

    def show_replace(self) -> None:
        self.search_bar.show_replace()

    def _find_next(self) -> None:
        self.search_bar.find_next()

    def _find_previous(self) -> None:
        self.search_bar.find_previous()

    def _on_editor_content_change(self, editor: Editor) -> None:
        if editor is self.current_editor():
            self.search_bar.on_editor_changed()

    # ------------------------------------------------------------------
    # Settings controls
    # ------------------------------------------------------------------
    def _apply_setting_widgets(self) -> None:
        width = int(self.settings.get("tab_width"))
        use_spaces = bool(self.settings.get("use_spaces"))
        self.tab_status.configure(text=f"Tab {width} · {'空格' if use_spaces else 'Tab'}")

    def _apply_tab_settings(self, width: int, use_spaces: bool) -> None:
        self.settings.set("tab_width", width)
        self.settings.set("use_spaces", use_spaces)
        for editor in self.editors:
            editor.set_tab_width(width)
            editor.set_use_spaces(use_spaces)
        self._apply_setting_widgets()
        self._refresh_status()
        self._set_status(
            f"缩进：{width} 个{'空格' if use_spaces else '制表符'}", "info"
        )

    def zoom_editor(self, delta: int) -> None:
        size = max(8, min(24, int(self.settings.get("font_size", 11)) + delta))
        self.settings.set("font_size", size)
        for editor in self.editors:
            editor.set_font_size(size)
        self._set_status(f"编辑器字号：{size} pt", "info")

    def reset_zoom(self) -> None:
        self.settings.set("font_size", 11)
        for editor in self.editors:
            editor.set_font_size(11)
        self._set_status("编辑器字号已重置", "info")

    def open_indent_dialog(self) -> None:
        if self._indent_dialog is not None and self._indent_dialog.winfo_exists():
            self._indent_dialog.lift()
            self._indent_dialog.focus_set()
            return
        self._indent_dialog = IndentDialog(
            self,
            int(self.settings.get("tab_width")),
            bool(self.settings.get("use_spaces")),
            self._apply_tab_settings,
        )

    def open_shortcuts(self) -> None:
        if self._shortcuts_dialog is not None and self._shortcuts_dialog.winfo_exists():
            self._shortcuts_dialog.lift()
            return
        self._shortcuts_dialog = ShortcutsDialog(self)

    def open_about(self) -> None:
        if self._about_dialog is not None and self._about_dialog.winfo_exists():
            self._about_dialog.lift()
            return
        self._about_dialog = AboutDialog(
            self,
            self.toolchain.version,
            self.toolchain.fpc or "",
        )

    # ------------------------------------------------------------------
    # Tabs and documents
    # ------------------------------------------------------------------
    def current_editor(self) -> Editor | None:
        if 0 <= self.active_index < len(self.editors):
            return self.editors[self.active_index]
        return None

    def _next_untitled_name(self) -> str:
        while True:
            self.untitled_counter += 1
            name = f"未命名-{self.untitled_counter}.pas"
            if not any(
                editor.path is None and editor.display_name == name
                for editor in self.editors
            ):
                return name

    def _start_initial(self, initial_files: list[str] | None) -> None:
        opened = False
        if initial_files:
            for raw in initial_files:
                path = Path(raw).expanduser()
                if path.exists() and path.is_file():
                    if self._load_path(path, activate=False) is not None:
                        opened = True
                elif str(raw):
                    # Allow `pascal-box new-file.pas` to create an empty
                    # document with that target path.
                    self._create_tab(
                        content="",
                        path=path.resolve(),
                        display_name=path.name,
                        activate=False,
                    )
                    opened = True
            if opened and self.editors:
                self._switch_tab(0)
        if not self.editors:
            self._create_tab(
                content=STARTER,
                display_name=self._next_untitled_name(),
                activate=True,
            )
        self._refresh_tabbar()
        self._update_title()

    def _create_tab(
        self,
        *,
        content: str = "",
        path: Path | None = None,
        source: SourceText | None = None,
        display_name: str | None = None,
        activate: bool = True,
    ) -> Editor:
        editor = Editor(
            self.editor_host,
            font_size=int(self.settings.get("font_size", 11)),
            tab_width=int(self.settings.get("tab_width")),
            use_spaces=bool(self.settings.get("use_spaces")),
            on_state_change=self._on_editor_state,
            on_cursor=self._on_editor_cursor,
            on_content_change=self._on_editor_content_change,
        )
        self.editors.append(editor)
        index = len(self.editors) - 1
        if path is not None:
            editor.path = path
            editor.display_name = display_name or path.name
            editor.encoding = "utf-8"
            editor.encoding_label = "UTF-8"
            editor.newline = "\r\n"
        else:
            editor.display_name = display_name or self._next_untitled_name()
        if source is not None:
            editor.encoding = source.encoding
            editor.encoding_label = source.encoding_label
            editor.newline = source.newline
        self._bind_editor_shortcuts(editor.text)
        editor.set_content(content)
        if activate:
            self._switch_tab(index)
        self._refresh_tabbar()
        return editor

    def new_file(self) -> None:
        self._create_tab(content="", activate=True)
        self._set_status("已新建空白文件", "info")
        editor = self.current_editor()
        if editor is not None:
            editor.focus_editor()

    def _switch_tab(self, index: int) -> None:
        if not (0 <= index < len(self.editors)):
            return
        previous = self.current_editor()
        if previous is not None and previous is not self.editors[index]:
            previous.pack_forget()
        self.active_index = index
        editor = self.editors[index]
        if not editor.winfo_ismapped():
            editor.pack(fill="both", expand=True)
        self.tabbar.set_active(index)
        self._update_title()
        self._refresh_status()
        if self.search_bar.visible:
            self.search_bar.on_editor_changed()
            self.search_bar.lift()
        editor.focus_editor()

    def _refresh_tabbar(self) -> None:
        tabs = [
            {"title": editor.display_name, "dirty": editor.dirty}
            for editor in self.editors
        ]
        self.tabbar.set_tabs(tabs, self.active_index)

    def _reorder_tab(self, old: int, new: int) -> None:
        if old == new:
            return
        if not (0 <= old < len(self.editors) and 0 <= new < len(self.editors)):
            return
        editor = self.editors.pop(old)
        self.editors.insert(new, editor)
        if self.active_index == old:
            self.active_index = new
        elif old < self.active_index <= new:
            self.active_index -= 1
        elif new <= self.active_index < old:
            self.active_index += 1
        self._refresh_tabbar()

    def _update_title(self) -> None:
        editor = self.current_editor()
        if editor is None:
            self.title("Pascal Box")
            return
        marker = "*" if editor.dirty else ""
        folder = ""
        if editor.path is not None:
            folder = f"  ·  {editor.path.parent}"
        self.title(f"{marker}{editor.display_name}{folder} — Pascal Box")

    def _on_editor_state(self, editor: Editor) -> None:
        self._refresh_tabbar()
        if editor is self.current_editor():
            self._update_title()
            self._refresh_status()

    def _on_editor_cursor(
        self, editor: Editor, line: int, column: int, line_count: int, chars: int
    ) -> None:
        if editor is not self.current_editor():
            return
        self.cursor_status.configure(text=f"行 {line}，列 {column}")
        self.lines_status.configure(text=f"{line_count} 行")
        self.encoding_status.configure(text=editor.encoding_label)
        self.eol_status.configure(text="CRLF" if editor.newline == "\r\n" else "LF")

    def _confirm_close_editor(self, editor: Editor) -> bool:
        if not editor.dirty:
            return True
        index = self._index_of(editor)
        if index >= 0 and index != self.active_index:
            self._switch_tab(index)
        answer = messagebox.askyesnocancel(
            "未保存的更改",
            f"{editor.display_name} 有未保存的更改。\n\n是否在关闭前保存？",
            parent=self,
        )
        if answer is None:
            return False
        if answer:
            return self._save_tab(editor)
        return True

    def _close_tab(self, index: int) -> None:
        if not (0 <= index < len(self.editors)):
            return
        editor = self.editors[index]
        if not self._confirm_close_editor(editor):
            return
        was_active = index == self.active_index
        try:
            editor.pack_forget()
            editor.destroy()
        except tk.TclError:
            pass
        self.editors.pop(index)
        if not self.editors:
            self.active_index = -1
            self._create_tab(content="", activate=True)
            self._set_status("就绪", "ready")
            return
        if was_active:
            new_index = min(index, len(self.editors) - 1)
            self.active_index = -1
            self._switch_tab(new_index)
        else:
            if index < self.active_index:
                self.active_index -= 1
            self._refresh_tabbar()
            self._refresh_status()
        self._update_title()
        self._set_status("标签已关闭", "info")

    def close_current(self) -> None:
        if self.active_index >= 0:
            self._close_tab(self.active_index)

    def cycle_tab(self, delta: int) -> None:
        if len(self.editors) < 2:
            return
        index = (self.active_index + delta) % len(self.editors)
        self._switch_tab(index)

    def _index_of(self, editor: Editor) -> int:
        for index, candidate in enumerate(self.editors):
            if candidate is editor:
                return index
        return -1

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _open_dialog(self) -> None:
        initial = self.settings.get("last_dir") or str(Path.home())
        paths = filedialog.askopenfilenames(
            parent=self,
            title="打开 Pascal 文件",
            initialdir=initial,
            filetypes=[
                ("Pascal 源文件", "*.pas *.pp *.lpr *.inc"),
                ("所有文件", "*.*"),
            ],
        )
        if paths:
            self.open_paths(list(paths))

    def open_paths(self, paths: list[str], *, quiet: bool = False) -> None:
        errors: list[str] = []
        opened: list[Editor] = []
        for raw in paths:
            path = Path(raw).expanduser()
            if not path.exists():
                errors.append(f"{path}：文件不存在")
                continue
            if not path.is_file():
                errors.append(f"{path}：不是文件")
                continue
            editor = self._load_path(path, activate=False)
            if editor is not None:
                opened.append(editor)
            else:
                errors.append(f"{path}：无法读取")
        if opened:
            self._switch_tab(self._index_of(opened[-1]))
            self._set_status(f"已打开 {opened[-1].display_name}", "info")
        if errors and not quiet:
            messagebox.showerror("打开失败", "\n".join(errors), parent=self)

    def _load_path(self, path: Path, *, activate: bool = True) -> Editor | None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        existing = self._editor_for_path(resolved)
        if existing is not None:
            if activate:
                self._switch_tab(self._index_of(existing))
            return existing
        try:
            source = read_source_file(resolved)
        except OSError as exc:
            messagebox.showerror("打开失败", f"{resolved}\n\n{exc}", parent=self)
            return None
        editor = self._create_tab(
            content=source.text,
            path=resolved,
            source=source,
            display_name=resolved.name,
            activate=activate,
        )
        self.settings.set("last_dir", str(resolved.parent))
        if activate:
            self._set_status(f"已打开 {resolved.name}", "info")
        return editor

    def save_current(self) -> bool:
        editor = self.current_editor()
        if editor is None:
            return False
        return self._save_tab(editor)

    def save_current_as(self) -> bool:
        editor = self.current_editor()
        if editor is None:
            return False
        return self._save_tab(editor, save_as=True)

    def save_all(self) -> bool:
        for index, editor in enumerate(list(self.editors)):
            if editor.dirty or editor.path is None:
                if editor.path is None:
                    self._switch_tab(index)
                if not self._save_tab(editor):
                    return False
        self._set_status("所有文件已保存", "ok")
        return True

    def _save_tab(self, editor: Editor, *, save_as: bool = False) -> bool:
        path = editor.path
        if path is None or save_as:
            initial_dir = self.settings.get("last_dir") or str(Path.home())
            if editor.path is not None:
                initial_dir = str(editor.path.parent)
            chosen = filedialog.asksaveasfilename(
                parent=self,
                title="保存 Pascal 文件",
                initialdir=initial_dir,
                initialfile=editor.display_name or "未命名.pas",
                defaultextension=".pas",
                filetypes=[
                    ("Pascal 源文件", "*.pas"),
                    ("所有文件", "*.*"),
                ],
            )
            if not chosen:
                return False
            path = Path(chosen)
            editor.path = path.resolve()
            editor.display_name = editor.path.name
            if editor.path.suffix.lower() in (".pas", ".pp", ".lpr", ".inc"):
                editor.encoding = editor.encoding or "utf-8"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_source_file(path, editor.get_content(), editor.encoding, editor.newline)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror(
                "保存失败", f"无法保存 {editor.display_name}：\n\n{exc}", parent=self
            )
            return False
        editor.mark_saved()
        self.settings.set("last_dir", str(path.parent))
        self._refresh_tabbar()
        self._update_title()
        self._refresh_status()
        self._set_status(f"已保存 · {editor.display_name}", "ok")
        return True

    def _editor_for_path(self, path: Path) -> Editor | None:
        target = self._path_key(path)
        for editor in self.editors:
            if editor.path is not None and self._path_key(editor.path) == target:
                return editor
        return None

    @staticmethod
    def _path_key(path: Path) -> str:
        try:
            value = str(path.resolve())
        except OSError:
            value = str(path)
        return os.path.normcase(value)

    def select_editor(self, editor: Editor) -> None:
        index = self._index_of(editor)
        if index >= 0:
            self._switch_tab(index)

    # ------------------------------------------------------------------
    # Output pane
    # ------------------------------------------------------------------
    def toggle_output(self, force: bool | None = None) -> None:
        if force is None:
            show = not self._output_visible
        else:
            show = bool(force)
        if show == self._output_visible:
            return
        self._output_visible = show
        if show:
            self.splitter.grid(row=3, column=0, sticky="ew")
            self.output_panel.grid(row=4, column=0, sticky="nsew")
            self._draw_splitter()
        else:
            self.splitter.grid_remove()
            self.output_panel.grid_remove()
        self.settings.set("output_visible", show)
        self._set_status("编译输出已显示" if show else "编译输出已收起", "info")

    def clear_output(self) -> None:
        try:
            self.compile_text.configure(state="normal")
            self.compile_text.delete("1.0", "end")
            self.compile_text.configure(state="disabled")
        except tk.TclError:
            return
        self._set_status("编译输出已清空", "info")

    def _clear_output_widget(self, widget: tk.Text) -> None:
        try:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")
        except tk.TclError:
            pass

    @staticmethod
    def _at_bottom(widget: tk.Text) -> bool:
        try:
            first, last = widget.yview()
            return last >= 0.999
        except tk.TclError:
            return True

    def _append_compile_header(self, text: str) -> None:
        widget = self.compile_text
        try:
            widget.configure(state="normal")
            widget.insert("end", text, "meta")
            widget.configure(state="disabled")
            widget.see("end-1c")
        except tk.TclError:
            pass

    def _insert_compile_line(self, line: str, base_dir: Path) -> None:
        widget = self.compile_text
        if not line:
            return
        try:
            widget.configure(state="normal")
            start = widget.index("end-1c")
            lower = line.lower()
            tag = "stdout"
            if "error:" in lower or "fatal:" in lower or "错误:" in line:
                tag = "err"
            elif "warning:" in lower or "警告:" in line:
                tag = "warn"
            elif "note:" in lower or "hint:" in lower or "提示:" in line:
                tag = "muted"
            elif line.startswith("Free Pascal Compiler"):
                tag = "muted"
            widget.insert("end", line, tag)
            end = widget.index("end-1c")
            match = COMPILE_ERROR_RE.match(line.rstrip("\r\n"))
            if match and not (
                match.group("severity") == "Fatal"
                and "There were" in match.group("message")
            ):
                self._add_compile_link(start, end, match, base_dir, tag)
            widget.configure(state="disabled")
        except tk.TclError:
            pass

    def _add_compile_link(
        self, start: str, end: str, match: re.Match, base_dir: Path, base_tag: str
    ) -> None:
        self._link_seq += 1
        tag_name = f"compile_link_{self._link_seq}"
        path = match.group("path")
        line_no = int(match.group("line"))
        col_no = int(match.group("col") or 1)
        widget = self.compile_text
        widget.tag_add(tag_name, start, end)
        widget.tag_configure(
            tag_name,
            foreground=Color.RED if base_tag == "err" else Color.YELLOW,
            underline=True,
        )
        widget.tag_bind(
            tag_name,
            "<Double-Button-1>",
            lambda _event, p=path, l=line_no, c=col_no, d=base_dir: self._jump_to_error(
                p, l, c, d
            ),
        )
        widget.tag_bind(
            tag_name, "<Enter>", lambda _event: widget.configure(cursor="hand2")
        )
        widget.tag_bind(
            tag_name, "<Leave>", lambda _event: widget.configure(cursor="arrow")
        )

    def _append_compile_result(self, output: str, base_dir: Path) -> None:
        widget = self.compile_text
        if not output:
            return
        stick = self._at_bottom(widget)
        if output and not output.endswith("\n"):
            output += "\n"
        for line in output.splitlines(keepends=True):
            self._insert_compile_line(line, base_dir)
        if stick:
            try:
                widget.see("end-1c")
            except tk.TclError:
                pass

    def _append_compile_summary(self, text: str, tag: str) -> None:
        widget = self.compile_text
        try:
            widget.configure(state="normal")
            if widget.index("end-1c") != "1.0":
                last = widget.get("end-2c", "end-1c")
                if last != "\n":
                    widget.insert("end", "\n")
            widget.insert("end", text + "\n", tag)
            widget.configure(state="disabled")
            widget.see("end-1c")
        except tk.TclError:
            pass

    def _jump_to_error(self, raw_path: str, line: int, col: int, base_dir: Path) -> None:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        if not candidate.exists():
            current = self.current_editor()
            if current is not None and current.path is not None:
                alternative = current.path.parent / raw_path
                if alternative.exists():
                    candidate = alternative
        if candidate.exists():
            editor = self._editor_for_path(candidate)
            if editor is None:
                editor = self._load_path(candidate, activate=True)
            if editor is not None:
                self._switch_tab(self._index_of(editor))
                editor.scroll_to(line, col)
                self._set_status(
                    f"已跳转到 {candidate.name}:{line}:{col}", "info"
                )
                return
        editor = self.current_editor()
        if editor is not None:
            editor.scroll_to(line, col)
            self._set_status(f"已跳转到第 {line} 行（文件未找到：{raw_path}）", "warn")
        else:
            self._set_status(f"无法跳转：{raw_path}", "error")

    # ------------------------------------------------------------------
    # Build and run
    # ------------------------------------------------------------------
    def _build_guard(self) -> Editor | None:
        if self._compile_busy:
            self._set_status("正在编译，请稍候…", "working")
            return None
        if self.active_runner is not None and self.active_runner.running:
            self._set_status("程序正在终端中运行，请先停止程序（Ctrl+F2）再编译", "warn")
            return None
        editor = self.current_editor()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return None
        if not self._ensure_saved_for_build(editor):
            return None
        return editor

    def _ensure_saved_for_build(self, editor: Editor) -> bool:
        if editor.path is None:
            self._switch_tab(self._index_of(editor))
            if not self._save_tab(editor, save_as=True):
                self._set_status("已取消编译：文件尚未保存", "warn")
                return False
        elif editor.dirty:
            if not self._save_tab(editor):
                self._set_status("已取消编译：保存失败", "warn")
                return False
        return True

    def compile_current(self, then_run: bool = False) -> None:
        editor = self._build_guard()
        if editor is None or editor.path is None:
            return
        source = editor.path
        token = self._compile_token + 1
        self._compile_token = token
        self._compile_busy = True
        self._last_compile_dir = source.parent
        self._last_build = None
        self.toggle_output(True)
        self._clear_output_widget(self.compile_text)
        exe = self.toolchain.executable_for(source)
        command_text = f'fpc -Mobjfpc -Sh -O2 -vw -o"{exe}" "{source.name}"'
        self._append_compile_header(f"[编译] {source}\n")
        self._append_compile_header(f"$ {command_text}\n\n")
        self._set_status(f"正在编译 {source.name}…", "working")

        def worker_done(result: CompileResult) -> None:
            self._events.put(("compile", token, result, then_run))

        self.toolchain.compile_async(source, worker_done)

    def _on_compile_done(
        self, token: int, result: CompileResult, then_run: bool
    ) -> None:
        if token != self._compile_token:
            return
        self._compile_busy = False
        base_dir = result.source.parent if result.source else self._last_compile_dir
        self._append_compile_result(result.output, base_dir)
        errors, warnings = self._compile_counts(result)
        if result.ok:
            exe = result.exe_path.name if result.exe_path else ""
            extra = f" · {warnings} 个警告" if warnings else ""
            self._append_compile_summary(
                f"[完成] 编译成功 · {result.elapsed:.2f}s · {exe}{extra}", "ok"
            )
            self._set_status(f"编译成功 · {result.elapsed:.2f}s", "ok")
            self._last_build = result
            if then_run and result.exe_path is not None:
                source = result.source
                encoding = "utf-8"
                if source is not None:
                    open_editor = self._editor_for_path(source)
                    if open_editor is not None:
                        encoding = open_editor.encoding
                self._start_program(result.exe_path, base_dir, encoding)
        else:
            err_text = f" · {errors} 个错误" if errors else ""
            self._append_compile_summary(
                f"[失败] 编译未通过{err_text} · 退出码 {result.returncode}", "err"
            )
            self._set_status(f"编译失败{err_text}", "error")
            self.toggle_output(True)

    @staticmethod
    def _compile_counts(result: CompileResult) -> tuple[int, int]:
        output = result.output
        primary = len(ERROR_POSITION_RE.findall(output))
        summary = ERROR_SUMMARY_RE.search(output)
        if summary:
            errors = int(summary.group(1))
        elif primary:
            errors = primary
        elif not result.ok:
            errors = 1
        else:
            errors = 0
        warnings = len(WARNING_POSITION_RE.findall(output))
        return errors, warnings

    def run_current(self) -> None:
        if self._compile_busy:
            self._set_status("正在编译，请稍候…", "working")
            return
        if self.active_runner is not None and self.active_runner.running:
            self._set_status("程序已经在终端中运行", "warn")
            return
        editor = self.current_editor()
        if editor is None:
            self._set_status("没有打开的文件", "warn")
            return
        if editor.path is None:
            self._set_status("请先保存文件，再进行编译和运行", "warn")
            return
        exe = self.toolchain.executable_for(editor.path)
        if not exe.is_file():
            self.toggle_output(True)
            self._set_status("尚未编译，按 F6 生成可执行文件", "warn")
            return
        self._start_program(exe, editor.path.parent, editor.encoding)

    def _start_program(self, exe: Path, cwd: Path, encoding: str) -> None:
        if self.active_runner is not None and self.active_runner.running:
            self._set_status("程序已经在终端中运行", "warn")
            return
        token = self._run_token + 1
        self._run_token = token
        self._stop_requested = False
        runner = ProgramRunner()
        self.active_runner = runner

        def emit(
            event: tuple,
            current_token: int = token,
            current_runner: ProgramRunner = runner,
        ) -> None:
            self._events.put(("runner", current_token, current_runner, event))

        started = runner.start(exe, cwd, emit, encoding=encoding)
        if started:
            self._set_status(f"已在终端中运行 {exe.name}", "working")
        else:
            self.active_runner = None
            self._set_status("程序启动失败", "error")

    def _handle_runner_event(
        self, token: int, runner: ProgramRunner, event: tuple
    ) -> None:
        if token != self._run_token or runner is not self.active_runner:
            return
        kind = event[0] if event else ""
        if kind == "error":
            self.active_runner = None
            self._set_status(str(event[1]), "error")
        elif kind == "exit":
            code = int(event[1])
            self.active_runner = None
            if self._stop_requested:
                self._set_status("程序终端已关闭", "info")
            elif code == 0:
                self._set_status("程序已退出，代码 0", "ok")
            else:
                self._set_status(f"程序已退出，代码 {code}", "error")
            self._stop_requested = False
            editor = self.current_editor()
            if editor is not None:
                editor.focus_editor()

    def stop_program(self) -> None:
        runner = self.active_runner
        if runner is None or not runner.running:
            self._set_status("当前没有正在运行的程序", "info")
            return
        self._stop_requested = True
        runner.stop()
        self._set_status("正在关闭程序终端…", "warn")

    # ------------------------------------------------------------------
    # Event pump
    # ------------------------------------------------------------------
    def _poll_events(self) -> None:
        if self._closing:
            return
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            try:
                if event[0] == "compile":
                    _, token, result, then_run = event
                    self._on_compile_done(token, result, then_run)
                elif event[0] == "runner":
                    _, token, runner, payload = event
                    self._handle_runner_event(token, runner, payload)
            except Exception:
                # The IDE should never die because a background task produced
                # an unexpected message; surface it in the status bar instead.
                self._set_status("后台任务出现异常", "error")
        try:
            self._poll_job = self.after(35, self._poll_events)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        if self._closing:
            return
        for editor in list(self.editors):
            if not self._confirm_close_editor(editor):
                return
        self._closing = True
        runner = self.active_runner
        if runner is not None:
            runner.stop()
        self.destroy()

    def destroy(self) -> None:
        self._closing = True
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
        for menu in getattr(self, "menus", {}).values():
            try:
                menu.unpost()
            except Exception:
                pass
        super().destroy()

    def toggle_theme(self) -> None:
        old_theme = normalize_theme(str(self.settings.get("theme", "dark")))
        new_theme = "light" if old_theme == "dark" else "dark"
        old_palette = {name: getattr(Color, name) for name in Color.__dict__ if name.isupper()}
        apply_theme(new_theme)
        self.theme = new_theme
        self.settings.set("theme", new_theme)
        new_palette = {name: getattr(Color, name) for name in old_palette}
        color_map = {
            old_palette[name]: new_palette[name]
            for name in old_palette
            if old_palette[name] != new_palette[name]
        }

        def remap(value):
            return color_map.get(str(value).lower() if False else str(value), value)

        def refresh_widget(widget) -> None:
            if isinstance(widget, FlatButton):
                widget.refresh_theme()
            for option in (
                "bg", "fg", "foreground", "activebackground", "activeforeground",
                "highlightbackground", "highlightcolor", "selectbackground",
                "selectforeground", "insertbackground", "disabledforeground",
            ):
                try:
                    widget.configure(**{option: remap(widget.cget(option))})
                except tk.TclError:
                    pass
            if isinstance(widget, tk.Canvas):
                for item in widget.find_all():
                    for option in ("fill", "outline"):
                        try:
                            widget.itemconfigure(item, **{option: remap(widget.itemcget(item, option))})
                        except tk.TclError:
                            pass
            for child in widget.winfo_children():
                refresh_widget(child)

        refresh_widget(self)

        for editor in self.editors:
            editor.text.configure(
                bg=Color.EDITOR_BG, fg=Color.TEXT, insertbackground=Color.CARET,
                selectbackground=Color.SELECTION, selectforeground=Color.TEXT,
                inactiveselectbackground=Color.SELECTION_INACTIVE,
            )
            editor.gutter.configure(bg=Color.GUTTER_BG)
            editor.scrollbar.configure(bg=Color.EDITOR_BG)
            editor.text.tag_configure("current_line", background=Color.CURRENT_LINE)
            editor.text.tag_configure("bracket_match", background=Color.MATCH_BG, foreground=Color.MATCH_FG)
            editor.text.tag_configure("bracket_unmatched", background=Color.UNMATCHED_BG, foreground=Color.UNMATCHED_FG)
            editor.text.tag_configure("find_match", background=Color.MATCH_BG, foreground=Color.MATCH_FG)
            editor.text.tag_configure("find_current", background=Color.ACCENT, foreground=Color.TEXT_INVERSE)
            editor.highlighter._configure_tags()
            editor._run_highlight()
            editor._schedule_gutter(5)

        self.search_bar.refresh_theme()

        try:
            self.compile_text.configure(bg=Color.PANEL_BG, fg=Color.TEXT)
            tag_colors = {
                "meta": Color.ACCENT, "ok": Color.GREEN, "err": Color.RED,
                "warn": Color.YELLOW, "muted": Color.TEXT_FAINT,
                "stdout": Color.TEXT, "input": Color.BLUE, "header": Color.TEXT_DIM,
            }
            for tag, foreground in tag_colors.items():
                self.compile_text.tag_configure(tag, foreground=foreground)
        except tk.TclError:
            pass

        self.tabbar.configure(bg=Color.CHROME_ALT)
        self.tabbar.canvas.configure(bg=Color.CHROME_ALT)
        if hasattr(self.tabbar, "plus"):
            self.tabbar.plus.refresh_theme()
            self.tabbar.plus.configure(
                bg=Color.CHROME_ALT,
                highlightbackground=Color.BORDER_SOFT,
                activebackground=Color.BTN_HOVER,
            )
        self.tabbar._redraw()
        self._draw_splitter()
        self._apply_setting_widgets()
        self._apply_native_window_style()
        self._set_status(
            "已切换到亮色模式" if new_theme == "light" else "已切换到暗色模式",
            "info",
        )
