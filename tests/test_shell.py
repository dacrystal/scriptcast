# tests/test_shell.py
import pytest

from scriptcast.shell import get_adapter
from scriptcast.shell.bash import BashAdapter
from scriptcast.shell.zsh import ZshAdapter


def test_get_bash():
    assert isinstance(get_adapter("bash"), BashAdapter)


def test_get_zsh():
    assert isinstance(get_adapter("zsh"), ZshAdapter)


def test_get_full_path():
    assert isinstance(get_adapter("/bin/bash"), BashAdapter)


def test_get_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported shell"):
        get_adapter("fish")


def test_bash_preamble_contains_set_x():
    p = BashAdapter().tracing_preamble("+")
    assert "set -x" in p
    assert 'PS4="+ "' in p


def test_bash_preamble_custom_prefix():
    p = BashAdapter().tracing_preamble(">>")
    assert 'PS4=">> "' in p


def test_zsh_preamble_contains_xtrace():
    p = ZshAdapter().tracing_preamble("+")
    assert "setopt xtrace" in p
    assert 'PS4="+ "' in p


def test_bash_unescape_xtrace_is_identity():
    adapter = BashAdapter()
    text = "set prompt $'\\C-[[92m> \\C-[[0m'"
    assert adapter.unescape_xtrace(text) == text


def test_zsh_unescape_ctrl_bracket_to_esc():
    # \C-[ is zsh's notation for ESC (Ctrl+[, chr 27)
    result = ZshAdapter().unescape_xtrace("set prompt $'\\C-[[92m> \\C-[[0m'")
    assert result == "set prompt \x1b[92m> \x1b[0m"


def test_zsh_unescape_octal():
    result = ZshAdapter().unescape_xtrace("set prompt $'\\033[92m> \\033[0m'")
    assert result == "set prompt \x1b[92m> \x1b[0m"


def test_zsh_unescape_hex():
    result = ZshAdapter().unescape_xtrace("set prompt $'\\x1b[92m> \\x1b[0m'")
    assert result == "set prompt \x1b[92m> \x1b[0m"


def test_zsh_unescape_escape_letter():
    result = ZshAdapter().unescape_xtrace("set prompt $'\\e[92m> \\e[0m'")
    assert result == "set prompt \x1b[92m> \x1b[0m"


def test_zsh_unescape_standard_escapes():
    result = ZshAdapter().unescape_xtrace("$'\\n\\t\\r\\\\'")
    assert result == "\n\t\r\\"


def test_zsh_unescape_no_dollar_quote_unchanged():
    text = "set prompt '\\033[92m> \\033[0m'"
    assert ZshAdapter().unescape_xtrace(text) == text


def test_zsh_unescape_multiple_spans():
    result = ZshAdapter().unescape_xtrace("$'\\C-['foo$'\\C-['")
    assert result == "\x1bfoo\x1b"


def test_zsh_unescape_unknown_escape_passthrough():
    # \q is not a known escape — passes through unchanged
    result = ZshAdapter().unescape_xtrace("$'\\q'")
    assert result == "\\q"


def test_zsh_unescape_ctrl_out_of_range_passthrough():
    # \C-? would give chr(-1) — should passthrough, not crash
    result = ZshAdapter().unescape_xtrace("$'\\C-?'")
    assert result == "\\C-?"
