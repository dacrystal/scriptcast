# scriptcast/generator.py
import json
import re
import shlex
from collections import deque
from pathlib import Path

from .config import ScriptcastConfig
from .directives import build_directives


def _parse_sc_header(
    lines: list[str],
    base: ScriptcastConfig | None = None,
) -> ScriptcastConfig:
    """Parse .sc JSONL header + pre-scene set directives into a ScriptcastConfig.

    Reads the first line as a JSON header for width/height/directive-prefix.
    Then walks subsequent lines applying 'set' directives until the first 'scene'.
    If *base* is provided, its fields serve as defaults overridden by the header.
    """
    if not lines:
        return base.copy() if base is not None else ScriptcastConfig()

    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError:
        return base.copy() if base is not None else ScriptcastConfig()

    if base is not None:
        config = base.copy()
        config.directive_prefix = header.get("directive-prefix", config.directive_prefix)
        config.width = header.get("width", config.width)
        config.height = header.get("height", config.height)
    else:
        config = ScriptcastConfig(
            directive_prefix=header.get("directive-prefix", "SC"),
            width=header.get("width", 100),
            height=header.get("height", 28),
        )

    for raw in lines[1:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, list) or len(row) < 3:
            continue
        _, typ, text = row[0], row[1], row[2]
        if typ != "dir":
            continue
        parts = shlex.split(str(text))
        if not parts:
            continue
        if parts[0] == "scene":
            break
        if parts[0] == "set" and len(parts) >= 3:
            config.apply("set", parts[1:])

    return config


def build_config_from_sc_text(
    sc_text: str,
    base: ScriptcastConfig | None = None,
) -> ScriptcastConfig:
    """Parse .sc JSONL header and pre-scene set directives into a ScriptcastConfig."""
    return _parse_sc_header(sc_text.splitlines(), base)


def generate_from_sc(
    sc_path: Path,
    output_dir: Path,
    output_stem: str | None = None,
    *,
    split_scenes: bool = False,
    base: ScriptcastConfig | None = None,
) -> list[Path]:
    """Read a JSONL .sc file and write .cast file(s) to output_dir."""
    return generate_from_sc_text(
        sc_path.read_text(),
        output_dir,
        output_stem=output_stem or sc_path.stem,
        split_scenes=split_scenes,
        base=base,
    )


def generate_from_sc_text(
    sc_text: str,
    output_dir: Path,
    output_stem: str = "output",
    *,
    split_scenes: bool = False,
    base: ScriptcastConfig | None = None,
) -> list[Path]:
    """Convert JSONL .sc text to .cast file(s). Returns list of written paths.

    If *base* is provided, its fields serve as defaults for the generated config.
    Pre-scene ``set`` directives in the .sc text still override the base, so a
    theme passed as *base* acts as a template that the script can override.
    """
    lines = sc_text.splitlines()
    if not lines:
        return []

    header = json.loads(lines[0])
    pipeline_version = header.get("pipeline-version", 1)
    if pipeline_version not in (1, 2, 3):
        raise ValueError(f"Unsupported .sc pipeline-version: {pipeline_version}")

    config = _parse_sc_header(lines, base)
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
        if typ == "dir" and text.split()[0] == "scene":
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

    _overhead = {"set"}

    def _is_overhead_only(evts: list[tuple]) -> bool:
        return all(
            typ == "dir" and text.split()[0] in _overhead
            for _, typ, text in evts
        )

    return [
        (name, evts)
        for name, evts in scenes
        if not (name == "main" and _is_overhead_only(evts))
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
    # Build gen registry: directive name → directive instance
    # Uses handles attribute; directives without handles are recorder-only.
    all_directives = build_directives(active.directive_prefix, active.trace_prefix)
    gen_registry = {d.handles: d for d in all_directives if d.handles is not None}

    lines.append(json.dumps([round(cursor, 6), "o", "\x1b[2J\x1b[H"]))
    cursor += active.enter_wait / 1000.0

    queue: deque[tuple] = deque(events)
    while queue:
        event = queue.popleft()
        _, typ, text = event

        if typ == "dir":
            parts = text.split()
            name = parts[0] if parts else ""
            d = gen_registry.get(name)
            if d is not None:
                cursor, new_lines = d.gen(event, queue, active, cursor)
                lines.extend(new_lines)

        elif typ == "cmd":
            lines.append(json.dumps([round(cursor, 6), "o", active.prompt]))
            cursor += active.cmd_wait / 1000.0
            for char in text:
                cursor += active.type_speed / 1000.0
                lines.append(json.dumps([round(cursor, 6), "o", char]))
                if char == " ":
                    cursor += active.effective_word_pause_s
            cursor += active.type_speed / 1000.0
            lines.append(json.dumps([round(cursor, 6), "o", "\r\n"]))

        elif typ == "out":
            if active.cr_delay > 0 and '\r' in text:
                # Split before each bare \r (not \r\n) for progress-bar animation
                parts = re.split(r'(?=\r(?!\n))', text)
                for j, part in enumerate(parts):
                    if part:
                        lines.append(json.dumps([round(cursor, 6), "o", part]))
                    if j < len(parts) - 1:
                        cursor += active.cr_delay / 1000.0
            elif text:
                lines.append(json.dumps([round(cursor, 6), "o", text]))

    lines.append(json.dumps([round(cursor, 6), "o", active.prompt]))
    cursor += active.exit_wait / 1000.0
    lines.append(json.dumps([round(cursor, 6), "o", ""]))
    return lines, cursor
