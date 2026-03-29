# scriptcast/config.py
from __future__ import annotations
import copy
from dataclasses import dataclass

_INT_KEYS = {"type_speed", "cmd_wait", "input_wait", "exit_wait", "width", "height", "enter_wait"}
_STR_KEYS = {"theme", "prompt", "directive_prefix", "trace_prefix"}
_BOOL_KEYS = {"show_title", "split_scenes"}

@dataclass
class ScriptcastConfig:
    type_speed: int = 40      # ms per character when typing commands
    cmd_wait: int = 80        # ms after typing a command, before output appears
    input_wait: int = 80      # ms to pause before typing an InputLine response
    exit_wait: int = 120      # ms after last output line of a command
    enter_wait: int = 80      # ms to pause at scene start, after clear and optional title
    width: int = 100
    height: int = 28
    theme: str = "dark"
    prompt: str = "$ "
    directive_prefix: str = "SC"
    trace_prefix: str = "+"
    show_title: bool = False
    split_scenes: bool = False

    def apply(self, name: str, args: list[str]) -> None:
        """Apply an SC directive. Only 'set' directives mutate config; others are ignored."""
        if name != "set" or len(args) < 2:
            return
        key, value = args[0], args[1]
        if key in _INT_KEYS:
            setattr(self, key, int(value))
        elif key in _STR_KEYS:
            setattr(self, key, value)
        elif key in _BOOL_KEYS:
            setattr(self, key, value.lower() in ("1", "true", "yes"))

    def copy(self) -> ScriptcastConfig:
        return copy.copy(self)
