"""A small, allocation-conscious Object Pascal syntax highlighter.

The highlighter is also the source of truth for "code vs. comment/string"
information used by the bracket matcher.
"""

from __future__ import annotations

import bisect
import re
import tkinter as tk

from .theme import Color, font_mono


KEYWORDS = frozenset(
    """
    absolute abstract and array as asm begin case cdecl class const constructor
    destructor dispinterface div do downto else end except exports external far
    file finalization finally for forward function goto if implementation in
    inherited initialization inline interface is label library message mod near
    nil not object of on operator or out overload override package packed
    private procedure program property protected public published raise record
    register repeat resourcestring safecall set shl shr stdcall stringresource
    then threadvar to try type unit until uses var virtual while with xor
    """.split()
)

TYPES = frozenset(
    """
    ansichar ansistring boolean byte cardinal char comp currency double dword
    extended hresult int64 integer intptr longbool longint longword nativeint
    nativeuint olevariant pansichar pbyte pchar pcurrency pdouble pextended
    pinteger plongint pointer pshortstring psingle psmallint pstring ptext
    pwidechar pword qword rawbytestring real real48 shortint shortstring
    single sizeint sizeuint smallint string text textfile tdatetime tobject
    tclass tlist tstringlist uint64 unicodeString utf8string variant widechar
    widestring word
    """.split()
)

BUILTINS = frozenset(
    """
    abs arctan assign assignfile blockread blockwrite break chr close closefile
    concat continue copy cos dec delete dispose eof eoln erase exit exp filepos
    filesize fillchar finalize flush frac freemem getmem halt high inc include
    initialize insert int ioresult length ln low move new odd ord pos pred read
    readln release rename reset rewrite round runerror seek seekeof seekeoln
    setlength settextbuf sin sizeof sqr sqrt str succ trunc truncate upcase val
    write writeln format inttostr strtoint trystrtoint floattostr trim uppercase
    lowercase stringreplace wrapText
    """.split()
)

TAG_NAMES = ("syntax_keyword", "syntax_type", "syntax_builtin", "syntax_string",
             "syntax_number", "syntax_comment", "syntax_directive")

_NUMBER_RE = re.compile(
    r"(?:\$[0-9A-Fa-f]+|%[01]+|&[0-7]+|\d+(?:\.(?!\.)\d+)?(?:[eE][+-]?\d+)?)"
)


def _word_re():
    return re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


_WORD_RE = _word_re()


class PascalHighlighter:
    def __init__(self, text: tk.Text, font_size: int = 11) -> None:
        self.text = text
        self.font_size = font_size
        self.masked = bytearray()
        self.line_starts: list[int] = [0]
        self._configure_tags()

    # -- tags ---------------------------------------------------------------
    def _configure_tags(self) -> None:
        t = self.text
        t.tag_configure("syntax_keyword", foreground=Color.SYN_KEYWORD)
        t.tag_configure("syntax_type", foreground=Color.SYN_TYPE)
        t.tag_configure("syntax_builtin", foreground=Color.SYN_BUILTIN)
        t.tag_configure("syntax_string", foreground=Color.SYN_STRING)
        t.tag_configure("syntax_number", foreground=Color.SYN_NUMBER)
        t.tag_configure("syntax_comment", foreground=Color.SYN_COMMENT,
                        font=font_mono(self.font_size, slant="italic"))
        t.tag_configure("syntax_directive", foreground=Color.SYN_DIRECTIVE,
                        font=font_mono(self.font_size, slant="italic"))

    def set_font_size(self, size: int) -> None:
        self.font_size = size
        self.text.tag_configure("syntax_comment", font=font_mono(size, slant="italic"))
        self.text.tag_configure("syntax_directive", font=font_mono(size, slant="italic"))

    # -- index helpers ------------------------------------------------------
    def offset(self, index: str) -> int:
        """Absolute offset for a Tk line.column index (within current text)."""
        try:
            line_text, col_text = index.split(".")
            line = max(1, int(line_text)) - 1
            col = int(col_text)
        except (ValueError, AttributeError):
            return 0
        if not self.line_starts:
            return col
        if line >= len(self.line_starts):
            return self.line_starts[-1] + col
        return self.line_starts[line] + col

    def index(self, offset: int) -> str:
        if not self.line_starts:
            return "1.0"
        offset = max(0, offset)
        line = bisect.bisect_right(self.line_starts, offset) - 1
        line = max(0, min(line, len(self.line_starts) - 1))
        return f"{line + 1}.{offset - self.line_starts[line]}"

    # -- scanning -----------------------------------------------------------
    def highlight(self) -> None:
        text = self.text
        try:
            src = text.get("1.0", "end-1c")
        except tk.TclError:
            return
        spans, masked = self._scan(src)
        self.masked = masked
        for tag in TAG_NAMES:
            text.tag_remove(tag, "1.0", "end")

        # Convert absolute character offsets to Tk line.column indices and
        # batch all ranges per tag, which is substantially faster than one
        # tag_add call per token.
        starts = [0]
        for match in re.finditer("\n", src):
            starts.append(match.end())
        self.line_starts = starts
        if not spans:
            return

        def index(offset: int) -> str:
            line = bisect.bisect_right(starts, offset) - 1
            return f"{line + 1}.{offset - starts[line]}"

        grouped: dict[str, list[str]] = {}
        for tag, start, end in spans:
            if end <= start:
                continue
            ranges = grouped.setdefault(tag, [])
            ranges.append(index(start))
            ranges.append(index(end))
        for tag, ranges in grouped.items():
            if ranges:
                text.tag_add(tag, *ranges)

    def _scan(self, src: str) -> tuple[list[tuple[str, int, int]], bytearray]:
        spans: list[tuple[str, int, int]] = []
        n = len(src)
        masked = bytearray(n + 1)
        i = 0
        while i < n:
            c = src[i]

            # Line comment
            if c == "/" and i + 1 < n and src[i + 1] == "/":
                j = src.find("\n", i)
                if j < 0:
                    j = n
                spans.append(("syntax_comment", i, j))
                masked[i:j] = b"\x01" * (j - i)
                i = j
                continue

            # Brace comment / directive
            if c == "{":
                j = src.find("}", i + 1)
                end = n if j < 0 else j + 1
                tag = "syntax_directive" if i + 1 < n and src[i + 1] == "$" else "syntax_comment"
                spans.append((tag, i, end))
                masked[i:end] = b"\x01" * (end - i)
                i = end
                continue

            # Parenthesis-star comment / directive
            if c == "(" and i + 1 < n and src[i + 1] == "*":
                j = src.find("*)", i + 2)
                end = n if j < 0 else j + 2
                tag = "syntax_directive" if i + 2 < n and src[i + 2] == "$" else "syntax_comment"
                spans.append((tag, i, end))
                masked[i:end] = b"\x01" * (end - i)
                i = end
                continue

            # String literal ('' is an escaped apostrophe)
            if c == "'":
                j = i + 1
                while j < n:
                    if src[j] == "\n":
                        break
                    if src[j] == "'":
                        if j + 1 < n and src[j + 1] == "'":
                            j += 2
                            continue
                        j += 1
                        break
                    j += 1
                spans.append(("syntax_string", i, j))
                masked[i:j] = b"\x01" * (j - i)
                i = j
                continue

            # Number
            if c.isdigit() or c == "$" and i + 1 < n and src[i + 1] in "0123456789abcdefABCDEF":
                m = _NUMBER_RE.match(src, i)
                if m:
                    spans.append(("syntax_number", i, m.end()))
                    i = m.end()
                    continue
            if c == "%" and i + 1 < n and src[i + 1] in "01":
                m = _NUMBER_RE.match(src, i)
                if m:
                    spans.append(("syntax_number", i, m.end()))
                    i = m.end()
                    continue
            if c == "&" and i + 1 < n and src[i + 1] in "01234567":
                m = _NUMBER_RE.match(src, i)
                if m:
                    spans.append(("syntax_number", i, m.end()))
                    i = m.end()
                    continue

            # Identifier / keyword
            if c.isalpha() or c == "_":
                m = _WORD_RE.match(src, i)
                if m:
                    word = m.group(0)
                    lower = word.lower()
                    if lower in TYPES:
                        tag = "syntax_type"
                    elif lower in KEYWORDS:
                        tag = "syntax_keyword"
                    elif lower in BUILTINS:
                        tag = "syntax_builtin"
                    else:
                        tag = ""
                    if tag:
                        spans.append((tag, i, m.end()))
                    i = m.end()
                    continue

            i += 1
        return spans, masked
