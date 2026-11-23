"""Colour palette and typography for Pascal Box.

Everything in the UI is built from hard-edged frames, canvases and classic Tk
buttons.  There are deliberately no ttk themes (and therefore no rounded
corners) in the application chrome.
"""

from __future__ import annotations


class Color:
    # Base surfaces
    BG = "#0a0e13"
    CHROME = "#10151c"
    CHROME_ALT = "#0d1218"
    EDITOR_BG = "#0e131a"
    GUTTER_BG = "#0b1016"
    PANEL_BG = "#0a0f15"
    INPUT_BG = "#0c1117"

    # Lines and separators
    BORDER = "#26303b"
    BORDER_SOFT = "#1a222c"
    BORDER_BRIGHT = "#354252"

    # Text
    TEXT = "#d1dae5"
    TEXT_DIM = "#8492a3"
    TEXT_FAINT = "#566271"
    TEXT_INVERSE = "#171006"

    # Accent / semantic colours
    ACCENT = "#f0a44b"
    ACCENT_HOVER = "#ffb860"
    ACCENT_PRESSED = "#d88a31"
    GREEN = "#8fc986"
    RED = "#e57378"
    YELLOW = "#e7c07b"
    BLUE = "#7db5e2"
    PURPLE = "#c49ae8"
    CYAN = "#71c9c0"

    # Buttons
    BTN_BG = "#161d26"
    BTN_HOVER = "#202a36"
    BTN_PRESSED = "#2a3644"
    BTN_DISABLED_BG = "#11171e"
    BTN_DISABLED_FG = "#4b5663"

    # Editor
    CURRENT_LINE = "#131b24"
    SELECTION = "#27445f"
    SELECTION_INACTIVE = "#1c3144"
    MATCH_BG = "#4a3315"
    MATCH_FG = "#ffd28a"
    UNMATCHED_BG = "#481d21"
    UNMATCHED_FG = "#ff9ea2"
    CARET = "#ffb860"

    # Syntax
    SYN_KEYWORD = "#e9a35a"
    SYN_TYPE = "#70c7bd"
    SYN_BUILTIN = "#82b7e8"
    SYN_STRING = "#a8c982"
    SYN_NUMBER = "#d7a1e6"
    SYN_COMMENT = "#5e7080"
    SYN_DIRECTIVE = "#c99bea"
    SYN_DEFINITION = "#efdca4"

    # Scrollbar
    SCROLL_TRACK = "#0e131a"
    SCROLL_THUMB = "#303c49"
    SCROLL_THUMB_HOVER = "#465568"


LIGHT_COLORS = {
    "BG": "#f4f6f8", "CHROME": "#edf0f4", "CHROME_ALT": "#f7f8fa",
    "EDITOR_BG": "#ffffff", "GUTTER_BG": "#f2f4f7", "PANEL_BG": "#f8fafc",
    "INPUT_BG": "#ffffff", "BORDER": "#cbd3dc", "BORDER_SOFT": "#e2e6eb",
    "BORDER_BRIGHT": "#aab6c3", "TEXT": "#20262d", "TEXT_DIM": "#596673",
    "TEXT_FAINT": "#8793a1", "TEXT_INVERSE": "#ffffff",
    "ACCENT": "#c66a16", "ACCENT_HOVER": "#dd7d25", "ACCENT_PRESSED": "#a95710",
    "GREEN": "#3d7d46", "RED": "#b94b52", "YELLOW": "#9b7017", "BLUE": "#397bad",
    "PURPLE": "#7a57a5", "CYAN": "#25877d",
    "BTN_BG": "#eef1f4", "BTN_HOVER": "#e2e7ec", "BTN_PRESSED": "#d5dde5",
    "BTN_DISABLED_BG": "#edf0f3", "BTN_DISABLED_FG": "#a8afb7",
    "CURRENT_LINE": "#f1f5f8", "SELECTION": "#bed7ee", "SELECTION_INACTIVE": "#dce8f2",
    "MATCH_BG": "#ffe3ad", "MATCH_FG": "#7a4c00", "UNMATCHED_BG": "#ffd9dc",
    "UNMATCHED_FG": "#9e2f38", "CARET": "#c66a16",
    "SYN_KEYWORD": "#a44f00", "SYN_TYPE": "#08796d", "SYN_BUILTIN": "#286aa2",
    "SYN_STRING": "#587e2c", "SYN_NUMBER": "#8056a3", "SYN_COMMENT": "#70808f",
    "SYN_DIRECTIVE": "#7b4aa0", "SYN_DEFINITION": "#806116",
    "SCROLL_TRACK": "#edf0f3", "SCROLL_THUMB": "#b8c1cb", "SCROLL_THUMB_HOVER": "#97a4b2",
}


DARK_COLORS = {name: getattr(Color, name) for name in list(Color.__dict__) if name.isupper()}


def normalize_theme(theme: str | None) -> str:
    return "light" if str(theme).lower() == "light" else "dark"


def apply_theme(theme: str) -> None:
    theme = normalize_theme(theme)
    palette = LIGHT_COLORS if theme == "light" else DARK_COLORS
    for name, value in palette.items():
        setattr(Color, name, value)


class Font:
    UI = "Microsoft YaHei UI"
    MONO = "JetBrains Mono"
    MONO_FALLBACK = "Consolas"
    BRAND = "Bahnschrift SemiBold"


ACCENT_BAR = 3


def font_ui(size: int = 9, weight: str = "normal") -> tuple:
    return (Font.UI, size, weight)


def font_mono(size: int = 11, weight: str = "normal", slant: str = "roman") -> tuple:
    return (Font.MONO, size, weight, slant)
