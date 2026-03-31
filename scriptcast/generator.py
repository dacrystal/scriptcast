# scriptcast/generator.py
from __future__ import annotations
import json
from collections import deque
from pathlib import Path

from .config import ScriptcastConfig
from .directives import SetDirective, SleepDirective


def generate_from_sc(
    sc_path: Path,
    output_dir: Path,
    output_stem: str | None = None,
    *,
    show_title: bool = False,
    split_scenes: bool = False,
) -> list[Path]:
    """Read a JSONL .sc file and write .cast file(s) to output_dir."""
    return generate_from_sc_text(
        sc_path.read_text(),
        output_dir,
        output_stem=output_stem or sc_path.stem,
        show_title=show_title,
        split_scenes=split_scenes,
    )


def generate_from_sc_text(
    sc_text: str,
    output_dir: Path,
    output_stem: str = "output",
    *,
    show_title: bool = False,
    split_scenes: bool = False,
) -> list[Path]:
    """Convert JSONL .sc text to .cast file(s). Returns list of written paths."""
    lines = sc_text.splitlines()
    if not lines:
        return []

    header = json.loads(lines[0])
    config = ScriptcastConfig(
        directive_prefix=header.get("directive-prefix", "SC"),
        width=header.get("width", 100),
        height=header.get("height", 28),
    )
    config.show_title = show_title
    config.split_scenes = split_scenes

    events: list[tuple] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        try:
            ts, typ, text = json.loads(line)
            events.append((float(ts), str(typ), str(text)))
        except (json.JSONDecodeError, ValueError):
            continue

    # Apply pre-scene set directives to base config
    for _, typ, text in events:
        if typ == "directive":
            parts = text.split()
            if parts[0] == "scene":
                break
            if parts[0] == "set" and len(parts) >= 3:
                config.apply("set", parts[1:])

    scenes = _split_scenes(events)

    if config.split_scenes:
        paths = []
        for scene_name, scene_events in scenes:
            content = _render_scene(scene_events, config.copy(), scene_name)
            path = output_dir / f"{scene_name}.cast"
            path.write_text(content)
            paths.append(path)
        return paths

    cast_header = {
        "version": 2,
        "width": config.width,
        "height": config.height,
        "timestamp": 0,
        "env": {"TERM": "xterm-256color"},
    }
    all_lines = [json.dumps(cast_header)]
    cursor = 0.0
    for scene_name, scene_events in scenes:
        scene_lines, cursor = _render_scene_lines(scene_events, config.copy(), scene_name, cursor)
        all_lines.extend(scene_lines)
    path = output_dir / f"{output_stem}.cast"
    path.write_text("\n".join(all_lines) + "\n")
    return [path]


def _split_scenes(events: list[tuple]) -> list[tuple[str, list[tuple]]]:
    scenes: list[tuple[str, list[tuple]]] = []
    current_name: str | None = None
    current_events: list[tuple] = []

    for event in events:
        _, typ, text = event
        if typ == "directive" and text.split()[0] == "scene":
            if current_name is not None:
                scenes.append((current_name, current_events))
            parts = text.split(maxsplit=1)
            current_name = parts[1] if len(parts) > 1 else "unnamed"
            current_events = []
        else:
            if current_name is None:
                current_name = "main"
            current_events.append(event)

    if current_name is not None:
        scenes.append((current_name, current_events))

    return [
        (name, evts)
        for name, evts in scenes
        if not (name == "main" and all(typ == "directive" for _, typ, _ in evts))
    ]


def _render_scene(
    events: list[tuple],
    config: ScriptcastConfig,
    scene_name: str,
) -> str:
    cast_header = {
        "version": 2,
        "width": config.width,
        "height": config.height,
        "timestamp": 0,
        "env": {"TERM": "xterm-256color"},
    }
    lines, _ = _render_scene_lines(events, config, scene_name, 0.0)
    return "\n".join([json.dumps(cast_header)] + lines) + "\n"


def _render_scene_lines(
    events: list[tuple],
    config: ScriptcastConfig,
    scene_name: str,
    initial_cursor: float = 0.0,
) -> tuple[list[str], float]:
    lines: list[str] = []
    cursor = initial_cursor
    active = config.copy()
    registry = {"set": SetDirective(), "sleep": SleepDirective()}

    lines.append(json.dumps([round(cursor, 6), "o", "\x1b[2J\x1b[H"]))
    if active.show_title:
        lines.append(json.dumps([round(cursor, 6), "o", f"{scene_name}\r\n"]))
    cursor += active.enter_wait / 1000.0

    queue: deque[tuple] = deque(events)
    while queue:
        event = queue.popleft()
        _, typ, text = event

        if typ == "directive":
            parts = text.split()
            name = parts[0] if parts else ""
            d = registry.get(name)
            if d is not None:
                cursor, new_lines = d.gen(event, queue, active, cursor)
                lines.extend(new_lines)

        elif typ == "cmd":
            lines.append(json.dumps([round(cursor, 6), "o", active.prompt]))
            for char in text:
                cursor += active.type_speed / 1000.0
                lines.append(json.dumps([round(cursor, 6), "o", char]))
            cursor += active.type_speed / 1000.0
            lines.append(json.dumps([round(cursor, 6), "o", "\r\n"]))
            cursor += active.cmd_wait / 1000.0

        elif typ == "output":
            next_typ = queue[0][1] if queue else None
            suffix = "" if next_typ == "input" else "\r\n"
            lines.append(json.dumps([round(cursor, 6), "o", text + suffix]))

        elif typ == "input":
            # Always add \r\n after input (Enter was pressed, visible or silent)
            cursor += active.input_wait / 1000.0
            for char in text:
                cursor += active.type_speed / 1000.0
                lines.append(json.dumps([round(cursor, 6), "o", char]))
            lines.append(json.dumps([round(cursor, 6), "o", "\r\n"]))

    cursor += active.exit_wait / 1000.0
    lines.append(json.dumps([round(cursor, 6), "o", ""]))
    return lines, cursor
