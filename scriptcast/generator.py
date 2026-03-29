# scriptcast/generator.py
from __future__ import annotations
import json
import re
import warnings
from pathlib import Path
from typing import Callable, Union

from .config import ScriptcastConfig
from .model import (
    CommandTrace, Directive, InputLine, OutputLine, PauseBlock, SceneStart, ScriptEvent
)


def _render_scene_events(
    events: list[ScriptEvent],
    config: ScriptcastConfig,
    scene_name: str,
    initial_cursor: float = 0.0,
) -> tuple[list[str], float]:
    """Render scene events to cast lines (no header). Returns (lines, final_cursor)."""
    lines: list[str] = []
    cursor = initial_cursor

    # Scene start: clear screen + optional title + enter_wait
    lines.append(json.dumps([round(cursor, 6), "o", "\x1b[2J\x1b[H"]))
    if config.show_title:
        lines.append(json.dumps([round(cursor, 6), "o", f"{scene_name}\r\n"]))
    cursor += config.enter_wait / 1000.0

    active = config.copy()
    filters: list[Callable[[str], str]] = []
    last_was_output = False

    for event in events:
        if isinstance(event, Directive):
            active.apply(event.name, event.args)
            if event.name == "filter" and event.args[:1] == ["sed"]:
                try:
                    filters.append(_compile_sed_filter(" ".join(event.args[1:])))
                except ValueError as e:
                    raise ValueError(f"Invalid SC filter: {e}") from e
            elif event.name == "sleep" and event.args:
                cursor += int(event.args[0]) / 1000.0

        elif isinstance(event, CommandTrace):
            if last_was_output:
                cursor += active.exit_wait / 1000.0
            # Emit prompt
            lines.append(json.dumps([round(cursor, 6), "o", active.prompt]))
            # Type command character by character
            for char in event.text:
                cursor += active.type_speed / 1000.0
                lines.append(json.dumps([round(cursor, 6), "o", char]))
            # Enter key
            cursor += active.type_speed / 1000.0
            lines.append(json.dumps([round(cursor, 6), "o", "\r\n"]))
            cursor += active.cmd_wait / 1000.0
            last_was_output = False

        elif isinstance(event, OutputLine):
            text = event.text
            for f in filters:
                text = f(text)
            lines.append(json.dumps([round(cursor, 6), "o", text + "\r\n"]))
            last_was_output = True

        elif isinstance(event, InputLine):
            cursor += active.input_wait / 1000.0
            for char in event.text:
                cursor += active.type_speed / 1000.0
                lines.append(json.dumps([round(cursor, 6), "o", char]))
            # Emit a zero-width marker so the input_wait delay is reflected in timestamps
            lines.append(json.dumps([round(cursor, 6), "o", ""]))
            last_was_output = False

        elif isinstance(event, PauseBlock):
            pass  # excluded from cast

    # Scene end: exit_wait always — emit a marker so the delay appears in timestamps
    cursor += active.exit_wait / 1000.0
    lines.append(json.dumps([round(cursor, 6), "o", ""]))

    return lines, cursor


def generate_scene(
    events: list[ScriptEvent],
    config: ScriptcastConfig,
    scene_name: str,
    initial_cursor: float = 0.0,
) -> str:
    """Render events to asciinema v2 cast content, including header."""
    header = {
        "version": 2,
        "width": config.width,
        "height": config.height,
        "timestamp": 0,
        "env": {"TERM": "xterm-256color"},
    }
    event_lines, _ = _render_scene_events(events, config, scene_name, initial_cursor)
    return "\n".join([json.dumps(header)] + event_lines) + "\n"


def generate_all_scenes(
    events: list[ScriptEvent],
    config: ScriptcastConfig,
    output_dir: Path,
    output_stem: str | None = None,
) -> list[Path]:
    """Split events by scene and write cast file(s). Returns created paths.

    In single-cast mode (default): one file named <output_stem>.cast.
    In split mode (config.split_scenes=True): one .cast per scene.
    """
    scenes = _split_scenes(events)

    if config.split_scenes:
        paths = []
        for scene_name, scene_events in scenes:
            content = generate_scene(scene_events, config.copy(), scene_name)
            path = output_dir / f"{scene_name}.cast"
            path.write_text(content)
            paths.append(path)
        return paths

    # Single-cast mode: all scenes in one file with continuing timestamps
    stem = output_stem or "output"
    header = {
        "version": 2,
        "width": config.width,
        "height": config.height,
        "timestamp": 0,
        "env": {"TERM": "xterm-256color"},
    }
    all_lines = [json.dumps(header)]
    cursor = 0.0
    for scene_name, scene_events in scenes:
        scene_lines, cursor = _render_scene_events(
            scene_events, config.copy(), scene_name, cursor
        )
        all_lines.extend(scene_lines)
    content = "\n".join(all_lines) + "\n"
    path = output_dir / f"{stem}.cast"
    path.write_text(content)
    return [path]


def _split_scenes(
    events: list[ScriptEvent],
) -> list[tuple[str, list[ScriptEvent]]]:
    """Split flat event list on SceneStart markers."""
    scenes: list[tuple[str, list[ScriptEvent]]] = []
    current_name: str | None = None
    current_events: list[ScriptEvent] = []
    for event in events:
        if isinstance(event, SceneStart):
            if current_name is not None:
                scenes.append((current_name, current_events))
            current_name = event.name
            current_events = []
        else:
            if current_name is None:
                current_name = "main"
            current_events.append(event)
    if current_name is not None:
        scenes.append((current_name, current_events))
    # Drop implicit "main" scene that contains only directives (global config lines)
    return [
        (name, evts)
        for name, evts in scenes
        if not (name == "main" and all(isinstance(e, Directive) for e in evts))
    ]


def _compile_sed_filter(expr: str) -> Callable[[str], str]:
    """Compile a sed s/pattern/replacement/flags expression to a Python callable."""
    # Strip surrounding shell quotes preserved by set -x tracing
    if len(expr) >= 2 and expr[0] in ('"', "'") and expr[-1] == expr[0]:
        expr = expr[1:-1]
    if not expr.startswith("s"):
        raise ValueError(f"Only s/// sed expressions are supported, got: {expr!r}")
    delim = expr[1]
    parts = expr[2:].split(delim)
    if len(parts) < 2:
        raise ValueError(f"Cannot parse sed expression: {expr!r}")
    pattern, replacement = parts[0], parts[1]
    flags_str = parts[2] if len(parts) > 2 else ""
    re_flags = re.IGNORECASE if "i" in flags_str else 0
    count = 0 if "g" in flags_str else 1
    compiled = re.compile(pattern, re_flags)
    return lambda text: compiled.sub(replacement, text, count=count)
