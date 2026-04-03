# scriptcast/config.py
from __future__ import annotations

import copy
from dataclasses import dataclass

_INT_KEYS = {
    "type_speed", "cmd_wait", "input_wait", "exit_wait",
    "width", "height", "enter_wait", "word_speed",
}
_STR_KEYS = {"terminal_theme", "prompt", "directive_prefix", "trace_prefix"}
_BOOL_KEYS = {"show_title", "split_scenes"}

@dataclass
class ScriptcastConfig:
    type_speed: int = 40      # ms per character when typing commands
    cmd_wait: int = 80        # ms after typing a command, before output appears
    input_wait: int = 80      # ms to pause before typing an InputLine response
    exit_wait: int = 120      # ms after last output line of a command
    enter_wait: int = 80      # ms to pause at scene start, after clear and optional title
    word_speed: int | None = None  # ms extra pause after each space; None = same as type_speed
    width: int = 100
    height: int = 28
    terminal_theme: str = "dark"          # was: theme
    prompt: str = "$ "
    directive_prefix: str = "SC"
    trace_prefix: str = "+"
    show_title: bool = False
    split_scenes: bool = False

    def apply(self, name: str, args: list[str]) -> None:
        """Apply an SC directive. Only 'set' directives mutate config; others are ignored."""
        if name != "set" or len(args) < 2:
            return
        key = args[0].replace("-", "_")   # normalise terminal-theme → terminal_theme
        value = args[1]
        if key in _INT_KEYS:
            setattr(self, key, int(value))
        elif key in _STR_KEYS:
            setattr(self, key, value)
        elif key in _BOOL_KEYS:
            setattr(self, key, value.lower() in ("1", "true", "yes"))

    def copy(self) -> ScriptcastConfig:
        return copy.copy(self)

    @property
    def effective_word_pause_s(self) -> float:
        """Pause to insert after each space when typing, in seconds."""
        ms = self.word_speed if self.word_speed is not None else self.type_speed
        return ms / 1000.0


@dataclass
class FrameConfig:
    # Inner padding — individual sides
    padding_top: int = 14
    padding_right: int = 14
    padding_bottom: int = 14
    padding_left: int = 14

    # Window appearance
    radius: int = 12
    border_color: str = "#ffffff30"   # RGBA hex
    border_width: int = 1

    # Outer background (None = no background)
    background: str | None = None     # "#hex" or "#hex1,#hex2" gradient

    # Outer margins — individual sides (None = auto: 0 if no bg, 82 if bg set)
    margin_top: int | None = None
    margin_right: int | None = None
    margin_bottom: int | None = None
    margin_left: int | None = None

    # Drop shadow
    shadow: bool = True
    shadow_color: str = "#0000004d"   # RGBA hex
    shadow_radius: int = 20
    shadow_offset_y: int = 21
    shadow_offset_x: int = 0

    # Title bar
    frame_bar: bool = True
    frame_bar_title: str = ""
    frame_bar_color: str = "#252535"
    frame_bar_buttons: bool = True

    # Watermark (opt-in)
    watermark: str | None = None
    watermark_color: str = "#ffffff"
    watermark_size: int | None = None

    # Frame style
    frame: bool = False

    # Scriptcast brand watermark (opt-out)
    scriptcast_watermark: bool = True
