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
