# scriptcast/parser.py
from __future__ import annotations
import warnings
from pathlib import Path
from typing import Union

from .config import ScriptcastConfig
from .model import (
    CommandTrace, Directive, InputLine, OutputLine, PauseBlock, SceneStart, ScriptEvent
)


def parse_sc_file(path: Union[str, Path]) -> tuple[ScriptcastConfig, list[ScriptEvent]]:
    return parse_sc_text(Path(path).read_text())


def parse_sc_text(text: str) -> tuple[ScriptcastConfig, list[ScriptEvent]]:
    lines = text.splitlines()
    header, body_lines = _split_header(lines)

    config = ScriptcastConfig(
        directive_prefix=header.get("directive-prefix", "SC"),
        trace_prefix=header.get("trace-prefix", "+"),
    )

    raw: list[ScriptEvent] = []
    for line in body_lines:
        event = _classify_line(line, config.trace_prefix, config.directive_prefix)
        if event is not None:
            raw.append(event)

    # Ensure at least one SceneStart
    if not any(isinstance(e, SceneStart) for e in raw):
        raw.insert(0, SceneStart(name="main"))

    events = _group_pauses(raw)

    # Apply global SC set directives (before first SceneStart) to config
    for event in events:
        if isinstance(event, SceneStart):
            break
        if isinstance(event, Directive):
            config.apply(event.name, event.args)

    return config, events


def _split_header(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    header: dict[str, str] = {}
    i = 0
    for i, line in enumerate(lines):
        if line.startswith("#"):
            key, _, value = line[1:].partition("=")
            header[key.strip()] = value.strip()
        else:
            break
    return header, lines[i:]


def _classify_line(
    line: str,
    trace_prefix: str,
    directive_prefix: str,
) -> ScriptEvent | None:
    # Strip timestamp prefix (first whitespace-delimited token)
    _, _, content = line.partition(" ")
    if not content:
        return None

    trace_marker = f"{trace_prefix} "
    if not content.startswith(trace_marker):
        # Check for SC mark input emitted by send_user in expect scripts
        if content.rstrip() == f": {directive_prefix} mark input":
            return InputLine()
        return OutputLine(text=content)

    rest = content[len(trace_marker):]

    # Suppress preamble noise (sourcing helper files)
    if rest.startswith("source ") or rest.startswith(". "):
        return None

    sc_marker = f": {directive_prefix} "
    if rest.startswith(sc_marker):
        parts = rest[len(sc_marker):].split()
        if not parts:
            return None
        name = parts[0].lower()
        args = parts[1:]
        if name == "scene":
            return SceneStart(name=args[0] if args else "unnamed")
        return Directive(name=name, args=args)

    return CommandTrace(text=rest)


def _group_pauses(events: list[ScriptEvent]) -> list[ScriptEvent]:
    result: list[ScriptEvent] = []
    i = 0
    while i < len(events):
        event = events[i]
        if (
            isinstance(event, Directive)
            and event.name == "record"
            and event.args[:1] == ["pause"]
        ):
            pause_events: list[ScriptEvent] = []
            i += 1
            found_resume = False
            while i < len(events):
                e = events[i]
                if (
                    isinstance(e, Directive)
                    and e.name == "record"
                    and e.args[:1] == ["resume"]
                ):
                    found_resume = True
                    i += 1
                    break
                pause_events.append(e)
                i += 1
            if not found_resume:
                warnings.warn("SC record pause without matching SC record resume", UserWarning)
            result.append(PauseBlock(events=pause_events))
        else:
            # Warn on orphaned resume (resume without prior pause)
            if (
                isinstance(event, Directive)
                and event.name == "record"
                and event.args[:1] == ["resume"]
            ):
                warnings.warn("SC record resume without prior SC record pause", UserWarning)
            else:
                result.append(event)
            i += 1
    return result
