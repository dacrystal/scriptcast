# scriptcast/config.py
from __future__ import annotations

import copy
import typing
from dataclasses import dataclass, field

_INT_KEYS = {
    "type_speed", "cmd_wait", "input_wait", "exit_wait",
    "width", "height", "enter_wait", "word_speed", "cr_delay",
}
_STR_KEYS = {"terminal_theme", "prompt", "directive_prefix", "trace_prefix"}
_BOOL_KEYS = {"split_scenes"}

_INT_THEME_PROPS = {
    "radius", "border-width",
    "shadow-radius", "shadow-offset-y", "shadow-offset-x", "watermark-size",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding-top", "padding-right", "padding-bottom", "padding-left",
}
_BOOL_THEME_PROPS = {"shadow", "frame-bar", "frame-bar-buttons", "frame", "scriptcast-watermark"}


def _parse_css_shorthand(value: str) -> tuple[int, int, int, int]:
    """Parse 1–4 space-separated ints using CSS shorthand rules (top, right, bottom, left)."""
    parts = value.split()
    if len(parts) == 1:
        v = int(parts[0])
        return (v, v, v, v)
    if len(parts) == 2:
        tb, lr = int(parts[0]), int(parts[1])
        return (tb, lr, tb, lr)
    if len(parts) == 3:
        t, lr, b = int(parts[0]), int(parts[1]), int(parts[2])
        return (t, lr, b, lr)
    if len(parts) == 4:
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    raise ValueError(f"CSS shorthand expects 1-4 values, got {len(parts)}: {value!r}")


@dataclass
class ThemeConfig:
    # Inner padding — individual sides
    padding_top: int = 14
    padding_right: int = 14
    padding_bottom: int = 14
    padding_left: int = 14

    # Window appearance
    radius: int = 12
    border_color: str = "ffffff30"   # RGBA hex, no # prefix
    border_width: int = 1

    # Outer background (None = no background)
    background: str | None = "1e1b4b,0d3b66"  # aurora gradient

    # Outer margins — individual sides (None = auto: 0 if no bg, 82 if bg set)
    margin_top: int | None = None
    margin_right: int | None = None
    margin_bottom: int | None = None
    margin_left: int | None = None

    # Drop shadow
    shadow: bool = True
    shadow_color: str = "0000004d"   # RGBA hex, no # prefix
    shadow_radius: int = 20
    shadow_offset_y: int = 21
    shadow_offset_x: int = 0

    # Title bar
    frame_bar: bool = True
    frame_bar_title: str = ""
    frame_bar_color: str = "252535"
    frame_bar_buttons: bool = True

    # Watermark (opt-in)
    watermark: str | None = None
    watermark_color: str = "ffffff"
    watermark_size: int | None = None

    # Frame style
    frame: bool = True

    # Scriptcast brand watermark (opt-out)
    scriptcast_watermark: bool = True

    def apply(self, key: str, value: str) -> None:
        """Apply a single theme key-value pair. key is dash-form without 'theme-' prefix."""
        if key == "margin":
            t, r, b, l = _parse_css_shorthand(value)
            self.margin_top, self.margin_right = t, r
            self.margin_bottom, self.margin_left = b, l
        elif key == "padding":
            t, r, b, l = _parse_css_shorthand(value)
            self.padding_top, self.padding_right = t, r
            self.padding_bottom, self.padding_left = b, l
        elif key in _INT_THEME_PROPS:
            setattr(self, key.replace("-", "_"), int(value))
        elif key in _BOOL_THEME_PROPS:
            setattr(self, key.replace("-", "_"), value.lower() in ("1", "true", "yes"))
        else:
            attr = key.replace("-", "_")
            if hasattr(self, attr):
                hints = typing.get_type_hints(type(self))
                hint = hints.get(attr)
                is_nullable = hint is not None and type(None) in typing.get_args(hint)
                setattr(self, attr, None if (value.lower() == "none" and is_nullable) else value)


@dataclass
class ScriptcastConfig:
    type_speed: int = 40      # ms per character when typing commands
    cmd_wait: int = 80        # ms after typing a command, before output appears
    input_wait: int = 80      # ms to pause before typing an InputLine response
    exit_wait: int = 120      # ms after last output line of a command
    enter_wait: int = 80      # ms to pause at scene start, after clear and optional title
    word_speed: int | None = None  # ms extra pause after each space; None = same as type_speed
    cr_delay: int = 0         # ms to wait between \r-split segments of an out event
    width: int = 100
    height: int = 28
    terminal_theme: str = "dark"          # was: theme
    prompt: str = "$ "
    directive_prefix: str = "SC"
    trace_prefix: str = "+"
    split_scenes: bool = False
    theme: ThemeConfig = field(default_factory=ThemeConfig)

    def apply(self, name: str, args: list[str]) -> None:
        """Apply an SC directive. Only 'set' directives mutate config; others are ignored."""
        if name != "set" or len(args) < 2:
            return
        raw_key = args[0]                      # original dash-form key
        key = raw_key.replace("-", "_")        # underscore-normalised
        value = " ".join(args[1:])             # join multi-word values (e.g. "14 0 0 0")
        if raw_key.startswith("theme-"):
            self.theme.apply(raw_key[6:], value)   # strip "theme-" prefix, pass dash form
        elif key in _INT_KEYS:
            setattr(self, key, int(value))
        elif key in _STR_KEYS:
            setattr(self, key, value)
        elif key in _BOOL_KEYS:
            setattr(self, key, value.lower() in ("1", "true", "yes"))

    def copy(self) -> ScriptcastConfig:
        return copy.deepcopy(self)

    @property
    def effective_word_pause_s(self) -> float:
        """Pause to insert after each space when typing, in seconds."""
        ms = self.word_speed if self.word_speed is not None else self.type_speed
        return ms / 1000.0
