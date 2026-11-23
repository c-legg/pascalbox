"""Hand-built, square-cornered Tk widgets used by the IDE chrome."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Iterable

from .theme import Color, Font, font_ui


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
class FlatButton(tk.Button):
    """A classic Tk button with flat colours and a crisp 1px border."""

    KINDS = {
        "primary": {
            "bg": Color.ACCENT,
            "fg": Color.TEXT_INVERSE,
            "hover": Color.ACCENT_HOVER,
            "active": Color.ACCENT_PRESSED,
            "border": Color.ACCENT,
        },
        "secondary": {
            "bg": Color.BTN_BG,
            "fg": Color.TEXT,
            "hover": Color.BTN_HOVER,
            "active": Color.BTN_PRESSED,
            "border": Color.BORDER,
        },
        "ghost": {
            "bg": Color.CHROME,
            "fg": Color.TEXT_DIM,
            "hover": Color.BTN_HOVER,
            "active": Color.BTN_PRESSED,
            "border": Color.CHROME,
        },
        "flat": {
            "bg": Color.CHROME_ALT,
            "fg": Color.TEXT_DIM,
            "hover": Color.BTN_HOVER,
            "active": Color.BTN_PRESSED,
            "border": Color.CHROME_ALT,
        },
        "danger": {
            "bg": Color.BTN_BG,
            "fg": Color.RED,
            "hover": Color.UNMATCHED_BG,
            "active": Color.UNMATCHED_BG,
            "border": Color.BORDER,
        },
    }

    def __init__(
        self,
        master,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        kind: str = "secondary",
        font=None,
        padx: int = 13,
        pady: int = 5,
        border: bool = True,
        width: int | None = None,
        anchor: str = "center",
        takefocus: bool = False,
        **kwargs,
    ) -> None:
        palette = dict(self.KINDS.get(kind, self.KINDS["secondary"]))
        live_palettes = {
            "primary": {"bg": Color.ACCENT, "fg": Color.TEXT_INVERSE, "hover": Color.ACCENT_HOVER, "active": Color.ACCENT_PRESSED, "border": Color.ACCENT},
            "secondary": {"bg": Color.BTN_BG, "fg": Color.TEXT, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.BORDER},
            "ghost": {"bg": Color.CHROME, "fg": Color.TEXT_DIM, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.CHROME},
            "flat": {"bg": Color.CHROME_ALT, "fg": Color.TEXT_DIM, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.CHROME_ALT},
            "danger": {"bg": Color.BTN_BG, "fg": Color.RED, "hover": Color.UNMATCHED_BG, "active": Color.UNMATCHED_BG, "border": Color.BORDER},
        }
        palette = dict(live_palettes.get(kind, live_palettes["secondary"]))
        palette.update(kwargs.pop("palette", {}))
        self._kind = kind
        self._normal_bg = palette["bg"]
        self._hover_bg = palette["hover"]
        self._active_bg = palette["active"]
        self._normal_fg = palette["fg"]
        self._border = palette["border"] if border else palette["bg"]
        self._enabled = True
        super().__init__(
            master,
            text=text,
            command=command,
            bg=palette["bg"],
            fg=palette["fg"],
            activebackground=palette["active"],
            activeforeground=palette["fg"],
            disabledforeground=Color.BTN_DISABLED_FG,
            relief="flat",
            overrelief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self._border,
            highlightcolor=self._border,
            font=font or font_ui(9),
            padx=padx,
            pady=pady,
            cursor="hand2",
            takefocus=takefocus,
            anchor=anchor,
            **kwargs,
        )
        if width is not None:
            self.configure(width=width)
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None) -> None:
        if self._enabled:
            self.configure(bg=self._hover_bg, highlightbackground=self._border)

    def _on_leave(self, _event=None) -> None:
        if self._enabled:
            self.configure(bg=self._normal_bg, highlightbackground=self._border)

    def refresh_theme(self) -> None:
        live_palettes = {
            "primary": {"bg": Color.ACCENT, "fg": Color.TEXT_INVERSE, "hover": Color.ACCENT_HOVER, "active": Color.ACCENT_PRESSED, "border": Color.ACCENT},
            "secondary": {"bg": Color.BTN_BG, "fg": Color.TEXT, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.BORDER},
            "ghost": {"bg": Color.CHROME, "fg": Color.TEXT_DIM, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.CHROME},
            "flat": {"bg": Color.CHROME_ALT, "fg": Color.TEXT_DIM, "hover": Color.BTN_HOVER, "active": Color.BTN_PRESSED, "border": Color.CHROME_ALT},
            "danger": {"bg": Color.BTN_BG, "fg": Color.RED, "hover": Color.UNMATCHED_BG, "active": Color.UNMATCHED_BG, "border": Color.BORDER},
        }
        palette = live_palettes.get(getattr(self, "_kind", "secondary"), live_palettes["secondary"])
        self._normal_bg = palette["bg"]
        self._hover_bg = palette["hover"]
        self._active_bg = palette["active"]
        self._normal_fg = palette["fg"]
        self._border = palette["border"]
        self.configure(
            bg=self._normal_bg,
            fg=self._normal_fg,
            activebackground=self._active_bg,
            activeforeground=self._normal_fg,
            disabledforeground=Color.BTN_DISABLED_FG,
            highlightbackground=self._border,
            highlightcolor=self._border,
        )

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if enabled:
            self.configure(
                state="normal",
                bg=self._normal_bg,
                fg=self._normal_fg,
                cursor="hand2",
            )
        else:
            self.configure(
                state="disabled",
                bg=Color.BTN_DISABLED_BG,
                fg=Color.BTN_DISABLED_FG,
                cursor="arrow",
            )


class Tooltip:
    """A delayed square tooltip for toolbar controls."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 550) -> None:
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip is not None or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.configure(bg=Color.BORDER_BRIGHT)
        label = tk.Label(
            self._tip,
            text=self.text,
            bg=Color.CHROME,
            fg=Color.TEXT_DIM,
            font=font_ui(8),
            padx=8,
            pady=4,
            justify="left",
        )
        label.pack(padx=1, pady=1)
        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


# ---------------------------------------------------------------------------
# Tab strip
# ---------------------------------------------------------------------------
class TabBar(tk.Frame):
    """A compact, custom-drawn document tab strip with square tabs."""

    def __init__(
        self,
        master,
        on_select: Callable[[int], None],
        on_close: Callable[[int], None],
        on_new: Callable[[], None],
        on_reorder: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(master, bg=Color.CHROME_ALT)
        self.on_select = on_select
        self.on_close = on_close
        self.on_new = on_new
        self.on_reorder = on_reorder
        self._tabs: list[dict] = []
        self._active = -1
        self._offset = 0
        self._hover: tuple[int, str] | None = None
        self._hit_rects: list[tuple[int, int, int, int, int]] = []
        self._content_width = 0
        self._press: tuple[int, int, bool] | None = None
        self._drag_index: int | None = None

        self.font = tkfont.Font(root=self, family=Font.UI, size=9)
        self.font_bold = tkfont.Font(root=self, family=Font.UI, size=9, weight="bold")

        self.canvas = tk.Canvas(
            self,
            bg=Color.CHROME_ALT,
            height=38,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.plus = FlatButton(
            self,
            text="+",
            kind="flat",
            command=self.on_new,
            font=("Segoe UI", 13),
            padx=0,
            pady=0,
            width=3,
            border=True,
        )
        self.plus.pack(side="right", fill="y")
        self.plus.configure(
            bg=Color.CHROME_ALT,
            highlightbackground=Color.BORDER_SOFT,
            activebackground=Color.BTN_HOVER,
        )
        Tooltip(self.plus, "新建文件  Ctrl+N")

        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-2>", self._on_middle)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    # -- public API ---------------------------------------------------------
    def set_tabs(self, tabs: Iterable[dict], active: int) -> None:
        self._tabs = list(tabs)
        self._active = active
        if self._drag_index is None:
            self._ensure_active_visible()
        self._redraw()

    def set_active(self, active: int) -> None:
        self._active = active
        self._ensure_active_visible()
        self._redraw()

    # -- geometry -----------------------------------------------------------
    def _tab_width(self, title: str, dirty: bool) -> int:
        base = self.font.measure(title)
        width = base + (62 if dirty else 50)
        return max(132, min(248, width))

    def _layout(self) -> list[dict]:
        layout = []
        x = 6 - self._offset
        for index, tab in enumerate(self._tabs):
            w = self._tab_width(str(tab.get("title", "未命名")), bool(tab.get("dirty")))
            layout.append({"index": index, "x": x, "w": w, "tab": tab})
            x += w
        self._content_width = x + self._offset + 6
        return layout

    def _viewport(self) -> int:
        return max(1, self.canvas.winfo_width())

    def _ensure_active_visible(self) -> None:
        if not (0 <= self._active < len(self._tabs)):
            self._offset = 0
            return
        x = 6
        total = 6
        for index, tab in enumerate(self._tabs):
            w = self._tab_width(str(tab.get("title", "未命名")), bool(tab.get("dirty")))
            if index == self._active:
                break
            x += w
            total += w
        active_w = self._tab_width(
            str(self._tabs[self._active].get("title", "未命名")),
            bool(self._tabs[self._active].get("dirty")),
        )
        total += active_w
        view = self._viewport()
        if total > view and x - self._offset + active_w > view - 8:
            self._offset = x + active_w - view + 12
        if x - self._offset < 6:
            self._offset = max(0, x - 6)
        self._offset = max(0, min(self._offset, max(0, total - view + 12)))

    # -- drawing ------------------------------------------------------------
    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        self._hit_rects = []
        width = max(1, c.winfo_width())
        height = max(1, c.winfo_height())
        c.create_rectangle(0, 0, width, height, fill=Color.CHROME_ALT, outline="")
        c.create_line(0, height - 1, width, height - 1, fill=Color.BORDER_SOFT)

        layout = self._layout()
        for item in layout:
            index = item["index"]
            x, w = item["x"], item["w"]
            if x + w < 0 or x > width:
                continue
            tab = item["tab"]
            active = index == self._active
            title = str(tab.get("title", "未命名"))
            dirty = bool(tab.get("dirty"))
            dragging = index == self._drag_index
            hovered = (
                self._drag_index is None
                and self._hover is not None
                and self._hover[0] == index
            )
            close_hovered = hovered and self._hover[1] == "close"

            if active:
                bg = Color.EDITOR_BG
            elif dragging:
                bg = Color.BTN_PRESSED
            elif hovered:
                bg = Color.BTN_HOVER
            else:
                bg = Color.CHROME_ALT
            c.create_rectangle(x, 0, x + w, height, fill=bg, outline="")
            if active:
                c.create_rectangle(x, 0, x + w, 2, fill=Color.ACCENT, outline="")
                c.create_line(x, height - 1, x + w, height - 1, fill=Color.EDITOR_BG)
            else:
                c.create_line(x + w - 1, 8, x + w - 1, height - 9, fill=Color.BORDER_SOFT)
            if dragging:
                c.create_rectangle(
                    x + 1, 1, x + w - 2, height - 2,
                    outline=Color.ACCENT, width=1,
                )

            text_x = x + 15
            if dirty:
                c.create_rectangle(
                    x + 14, height // 2 - 3, x + 20, height // 2 + 3,
                    fill=Color.ACCENT if active else Color.TEXT_FAINT,
                    outline="",
                )
                text_x = x + 28
            max_text = w - (text_x - x) - 38
            label = self._ellipsize(title, max_text)
            c.create_text(
                text_x,
                height // 2,
                text=label,
                anchor="w",
                fill=Color.TEXT if active else Color.TEXT_DIM,
                font=self.font_bold if active else self.font,
            )

            close_x = x + w - 17
            close_color = Color.RED if close_hovered else (
                Color.TEXT_DIM if active else Color.TEXT_FAINT
            )
            c.create_line(
                close_x - 4, height // 2 - 4, close_x + 4, height // 2 + 4,
                fill=close_color, width=1,
            )
            c.create_line(
                close_x - 4, height // 2 + 4, close_x + 4, height // 2 - 4,
                fill=close_color, width=1,
            )
            self._hit_rects.append(
                (x, x + w, index, close_x - 9, close_x + 9)
            )

    def _ellipsize(self, text: str, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if self.font.measure(text) <= max_width:
            return text
        ell = "…"
        ell_width = self.font.measure(ell)
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.font.measure(text[:mid]) + ell_width <= max_width:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + ell

    # -- events -------------------------------------------------------------
    def _tab_at(self, x: int) -> tuple[int, int, int] | None:
        for x1, x2, index, c1, c2 in self._hit_rects:
            if x1 <= x < x2:
                return index, c1, c2
        return None

    def _on_press(self, event) -> None:
        self._press = None
        self._drag_index = None
        hit = self._tab_at(event.x)
        if hit is None:
            self._hover = None
            self._redraw()
            return
        index, close1, close2 = hit
        self._press = (index, event.x, close1 <= event.x <= close2)

    def _on_drag(self, event) -> None:
        press = self._press
        if press is None:
            return
        index, start_x, on_close = press
        if self._drag_index is None:
            if on_close or abs(event.x - start_x) < 6:
                return
            if not (0 <= index < len(self._tabs)):
                return
            self._drag_index = index
            self._hover = None
            self.canvas.configure(cursor="fleur")
            self._redraw()

        if not (0 <= self._drag_index < len(self._tabs)):
            return
        self._auto_scroll(event.x)
        target = self._drop_index(event.x, self._drag_index)
        if target != self._drag_index:
            old = self._drag_index
            self._drag_index = target
            if self.on_reorder is not None:
                self.on_reorder(old, target)
            else:
                self._move_tab_local(old, target)
            self._redraw()

    def _on_release(self, event) -> None:
        press = self._press
        dragged = self._drag_index is not None
        self._press = None
        self._drag_index = None
        self._hover = None
        self.canvas.configure(cursor="arrow")
        if dragged:
            self._ensure_active_visible()
            self._redraw()
            return
        if press is None:
            return
        index, _start_x, on_close = press
        if not (0 <= index < len(self._tabs)):
            return
        if on_close:
            hit = self._tab_at(event.x)
            if hit is not None and hit[0] == index and hit[1] <= event.x <= hit[2]:
                self.on_close(index)
            else:
                self._redraw()
            return
        self.on_select(index)

    def _auto_scroll(self, x: int) -> None:
        self._layout()
        view = self._viewport()
        max_offset = max(0, self._content_width - view + 4)
        old = self._offset
        if x < 18:
            self._offset = max(0, self._offset - 12)
        elif x > view - 18:
            self._offset = min(max_offset, self._offset + 12)
        if self._offset != old:
            self._redraw()

    def _drop_index(self, x: int, dragging: int) -> int:
        layout = self._layout()
        if len(layout) <= 1:
            return 0
        slot = len(layout)
        for item in layout:
            if x < item["x"] + item["w"] / 2:
                slot = item["index"]
                break
        target = slot - 1 if slot > dragging else slot
        return max(0, min(len(layout) - 1, target))

    def _move_tab_local(self, old: int, new: int) -> None:
        tab = self._tabs.pop(old)
        self._tabs.insert(new, tab)
        if self._active == old:
            self._active = new
        elif old < self._active <= new:
            self._active -= 1
        elif new <= self._active < old:
            self._active += 1

    def _on_middle(self, event) -> None:
        hit = self._tab_at(event.x)
        if hit is not None:
            self.on_close(hit[0])

    def _on_motion(self, event) -> None:
        if self._drag_index is not None:
            return
        hit = self._tab_at(event.x)
        new_hover = None
        if hit is not None:
            index, close1, close2 = hit
            new_hover = (index, "close" if close1 <= event.x <= close2 else "tab")
        if new_hover != self._hover:
            self._hover = new_hover
            self._redraw()
        self.canvas.configure(cursor="hand2" if new_hover else "arrow")

    def _on_leave(self, _event=None) -> None:
        if self._drag_index is not None:
            return
        if self._hover is not None:
            self._hover = None
            self._redraw()
        self.canvas.configure(cursor="arrow")

    def _on_wheel(self, event) -> None:
        if self._drag_index is not None:
            return
        if self._content_width <= self._viewport():
            return
        step = 75 if event.delta < 0 else -75
        max_offset = max(0, self._content_width - self._viewport() + 4)
        self._offset = max(0, min(max_offset, self._offset + step))
        self._redraw()


# ---------------------------------------------------------------------------
# Scrollbar
# ---------------------------------------------------------------------------
class FlatScrollbar(tk.Canvas):
    """A slim, square scrollbar for Text and Canvas widgets."""

    def __init__(self, master, command: Callable, *, width: int = 11, bg: str = Color.EDITOR_BG):
        super().__init__(
            master,
            width=width,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.command = command
        self._first = 0.0
        self._last = 1.0
        self._hover = False
        self._dragging = False
        self._drag_offset = 0.0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)

    def set(self, first, last) -> None:
        try:
            self._first = float(first)
            self._last = float(last)
        except (TypeError, ValueError):
            self._first, self._last = 0.0, 1.0
        self._draw()

    def _thumb_geometry(self) -> tuple[int, int, int]:
        height = max(1, self.winfo_height())
        top = int(self._first * height)
        bottom = int(self._last * height)
        if bottom - top < 24:
            bottom = top + 24
            if bottom > height:
                bottom = height
                top = max(0, bottom - 24)
        return top, bottom, height

    def _draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        top, bottom, height = self._thumb_geometry()
        self.create_rectangle(0, 0, width, height, fill=Color.SCROLL_TRACK, outline="")
        if self._last - self._first >= 0.999:
            return
        fill = Color.SCROLL_THUMB_HOVER if (self._hover or self._dragging) else Color.SCROLL_THUMB
        self.create_rectangle(3, top + 2, width - 3, bottom - 2, fill=fill, outline="")

    def _enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event=None) -> None:
        if not self._dragging:
            self._hover = False
            self._draw()

    def _press(self, event) -> None:
        top, bottom, _height = self._thumb_geometry()
        if top <= event.y <= bottom:
            self._dragging = True
            self._drag_offset = event.y - top
        elif event.y < top:
            self.command("scroll", -1, "pages")
        else:
            self.command("scroll", 1, "pages")

    def _drag(self, event) -> None:
        if not self._dragging:
            return
        _top, _bottom, height = self._thumb_geometry()
        target = max(0.0, min(1.0, (event.y - self._drag_offset) / height))
        self.command("moveto", target)

    def _release(self, _event=None) -> None:
        self._dragging = False
        self._hover = self.winfo_pointerx() >= self.winfo_rootx() and self.winfo_pointerx() <= (
            self.winfo_rootx() + self.winfo_width()
        ) and self.winfo_pointery() >= self.winfo_rooty() and self.winfo_pointery() <= (
            self.winfo_rooty() + self.winfo_height()
        )
        self._draw()

    def _wheel(self, event) -> None:
        self.command("scroll", -1 if event.delta > 0 else 1, "units")


# ---------------------------------------------------------------------------
# Section tabs used by the output drawer
# ---------------------------------------------------------------------------
class SectionTab(tk.Frame):
    def __init__(
        self,
        master,
        text: str,
        command: Callable[[], None],
        *,
        bg: str = Color.CHROME,
    ) -> None:
        super().__init__(master, bg=bg, cursor="hand2")
        self._bg = bg
        self._active = False
        self.command = command
        self.label = tk.Label(
            self,
            text=text,
            bg=bg,
            fg=Color.TEXT_FAINT,
            font=font_ui(9),
            padx=14,
            pady=0,
            cursor="hand2",
        )
        self.label.pack(fill="both", expand=True, pady=(0, 2))
        self.indicator = tk.Frame(self, height=2, bg=bg)
        self.indicator.pack(fill="x", side="bottom")
        for widget in (self, self.label, self.indicator):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _click(self, _event=None) -> None:
        self.command()

    def _enter(self, _event=None) -> None:
        if not self._active:
            self.label.configure(fg=Color.TEXT)

    def _leave(self, _event=None) -> None:
        if not self._active:
            self.label.configure(fg=Color.TEXT_FAINT)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.label.configure(
            fg=Color.ACCENT if active else Color.TEXT_FAINT,
            font=font_ui(9, "bold" if active else "normal"),
        )
        self.indicator.configure(bg=Color.ACCENT if active else self._bg)
        self.configure(bg=self._bg)
        self.label.configure(bg=self._bg)
