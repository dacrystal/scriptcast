# scriptcast/theme.py
from __future__ import annotations

import dataclasses
import json
import re
import typing
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig, ScriptcastConfig

_BUILTIN_THEMES_DIR = Path(__file__).parent / "assets" / "themes"

# Matches:  : SC set <key> <value>
_SET_RE = re.compile(r":\s+SC\s+set\s+(\S+)\s+(.+?)\s*$")

_INT_THEME_PROPS = {
    "radius", "border-width",
    "shadow-radius", "shadow-offset-y", "shadow-offset-x", "watermark-size",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding-top", "padding-right", "padding-bottom", "padding-left",
}
_BOOL_THEME_PROPS = {"shadow", "frame-bar", "frame-bar-buttons"}


def _parse_css_shorthand(value: str) -> tuple[int, int, int, int]:
    """Parse 1–4 space-separated ints using CSS shorthand rules.

    Returns (top, right, bottom, left).
    1 value  → all sides equal
    2 values → top/bottom, left/right
    3 values → top, left/right, bottom
    4 values → top, right, bottom, left
    """
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


def parse_theme_file(path: Path) -> dict[str, str]:
    """Return all 'SC set' key-value pairs found in a .sh theme file."""
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = _SET_RE.search(line)
        if m:
            result[m.group(1)] = m.group(2)
    return result


def load_theme(name_or_path: str) -> dict[str, str]:
    """Load a theme by built-in name or file path. Built-in names take priority."""
    builtin = _BUILTIN_THEMES_DIR / f"{name_or_path}.sh"
    if builtin.exists():
        return parse_theme_file(builtin)
    path = Path(name_or_path)
    if path.exists():
        return parse_theme_file(path)
    raise FileNotFoundError(f"Theme not found: {name_or_path!r}")


def apply_theme_to_configs(
    theme: dict[str, str],
    frame_cfg: FrameConfig,
    sc_cfg: ScriptcastConfig,
) -> None:
    """Apply a parsed theme dict to FrameConfig and ScriptcastConfig in-place."""
    for key, value in theme.items():
        if key == "terminal-theme":
            sc_cfg.terminal_theme = value
        elif key.startswith("theme-"):
            prop = key[6:]  # strip "theme-" prefix
            if prop == "margin":
                t, r, b, l = _parse_css_shorthand(value)
                frame_cfg.margin_top = t
                frame_cfg.margin_right = r
                frame_cfg.margin_bottom = b
                frame_cfg.margin_left = l
            elif prop == "padding":
                t, r, b, l = _parse_css_shorthand(value)
                frame_cfg.padding_top = t
                frame_cfg.padding_right = r
                frame_cfg.padding_bottom = b
                frame_cfg.padding_left = l
            elif prop in _INT_THEME_PROPS:
                setattr(frame_cfg, prop.replace("-", "_"), int(value))
            elif prop in _BOOL_THEME_PROPS:
                setattr(frame_cfg, prop.replace("-", "_"), value.lower() in ("1", "true", "yes"))
            else:
                attr = prop.replace("-", "_")
                if hasattr(frame_cfg, attr):
                    # Only convert "none" → None for fields typed as nullable (str | None)
                    hints = typing.get_type_hints(type(frame_cfg))
                    hint = hints.get(attr)
                    is_nullable = hint is not None and type(None) in typing.get_args(hint)
                    setattr(frame_cfg, attr, None if (value.lower() == "none" and is_nullable) else value)


def scan_sc_for_theme(sc_path: Path) -> dict[str, str]:
    """Pre-scan a .sc JSONL file and return all theme-related 'SC set' directives."""
    result: dict[str, str] = {}
    for line in sc_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Skip the header (a dict, not a list)
        if not isinstance(row, list) or len(row) < 3:
            continue
        _, typ, text = row[0], row[1], row[2]
        if typ != "directive":
            continue
        parts = str(text).split()
        if len(parts) >= 3 and parts[0] == "set":
            key = parts[1]
            if key.startswith("theme-") or key == "terminal-theme":
                result[key] = " ".join(parts[2:])
    return result
