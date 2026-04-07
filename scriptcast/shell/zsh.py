# scriptcast/shell/zsh.py
import re

from .adapter import ShellAdapter

_ANSI_C_RE = re.compile(r"\$'((?:[^'\\]|\\.)*)'")
_SIMPLE_ESCAPES = {
    'n': '\n', 'r': '\r', 't': '\t', 'a': '\a',
    'b': '\b', 'f': '\f', 'v': '\v', "'": "'", '\\': '\\',
}


def _decode_ansi_c_body(body: str) -> str:
    """Decode the interior of a $'...' ANSI-C quoted string as produced by zsh xtrace."""
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != '\\' or i + 1 >= len(body):
            out.append(ch)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[nxt])
            i += 2
        elif nxt in ('e', 'E'):
            out.append('\x1b')
            i += 2
        elif nxt in ('C', 'c') and i + 3 < len(body) and body[i + 2] == '-':
            # \C-X → Ctrl+X; e.g. \C-[ → chr(91-64) = chr(27) = ESC
            code = ord(body[i + 3].upper()) - 64
            if 0 <= code <= 127:
                out.append(chr(code))
                i += 4
            else:
                out.append('\\')
                out.append(nxt)
                i += 2
        elif nxt == 'x':
            hex_str = body[i + 2:i + 4]
            if len(hex_str) == 2 and all(c in '0123456789abcdefABCDEF' for c in hex_str):
                out.append(chr(int(hex_str, 16)))
                i += 4
            else:
                out.append('\\')
                out.append(nxt)
                i += 2
        elif nxt in '01234567':
            j = i + 1
            while j < len(body) and j < i + 4 and body[j] in '01234567':
                j += 1
            out.append(chr(int(body[i + 1:j], 8)))
            i = j
        else:
            out.append('\\')
            out.append(nxt)
            i += 2
    return ''.join(out)


class ZshAdapter(ShellAdapter):
    @property
    def name(self) -> str:
        return "zsh"

    def tracing_preamble(self, trace_prefix: str) -> str:
        return f'PS4="{trace_prefix} "\nsetopt xtrace\n'

    def unescape_xtrace(self, text: str) -> str:
        """Expand $'...' ANSI-C spans in zsh xtrace directive text."""
        return _ANSI_C_RE.sub(lambda m: _decode_ansi_c_body(m.group(1)), text)
