# scriptcast/recorder.py
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import warnings
from pathlib import Path

from .config import ScriptcastConfig
from .directives import ScEvent
from .registry import build_directives
from .shell import get_adapter

_HEX_ESC_RE = re.compile(r"\\x([0-9a-fA-F]{2})")
_OCT_ESC_RE = re.compile(r"\\([0-7]{1,3})")


def _decode_bash_escapes(text: str) -> str:
    """Decode literal \\xNN hex and \\NNN octal escapes in an xtrace SC directive line.

    Bash xtrace passes raw bytes through (single-quoted), so actual ESC bytes
    need no decoding. This handles the case where the user writes double-quoted
    strings like "\\x1b[92m..." or "\\033[92m..." — bash keeps \\x1b/\\033 as
    literal text, which must be decoded to real Unicode code points so they are
    stored as \\u001b in the .sc JSONL.
    """
    text = _HEX_ESC_RE.sub(lambda m: chr(int(m.group(1), 16)), text)
    text = _OCT_ESC_RE.sub(lambda m: chr(int(m.group(1), 8)), text)
    return text


def _parse_raw(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> list[ScEvent]:
    """Parse raw xtrace log text into an initial list of ScEvents.

    Classification rules (applied per line):
      "+ : SC <rest>"  →  ScEvent(ts, "dir",  decode_escapes(rest))
      "+ <cmd>"        →  ScEvent(ts, "cmd",  cmd)
      "<text>"         →  ScEvent(ts, "out",  text)
    Lines with non-float timestamps are skipped.
    """
    sc_prefix = f"{trace_prefix} : {directive_prefix} "
    trace_prefix_sp = f"{trace_prefix} "
    events: list[ScEvent] = []
    for raw in raw_text.splitlines():
        ts_str, _, content = raw.partition(" ")
        try:
            ts = float(ts_str)
        except ValueError:
            continue
        content = content.rstrip("\n\r")
        if content.startswith(sc_prefix):
            rest = _decode_bash_escapes(content[len(sc_prefix):])
            events.append(ScEvent(ts, "dir", rest))
        elif content.startswith(trace_prefix_sp):
            events.append(ScEvent(ts, "cmd", content[len(trace_prefix_sp):]))
        else:
            events.append(ScEvent(ts, "out", content))
    return events


def _serialise(events: list[ScEvent]) -> str:
    """Convert a list of ScEvents to JSONL text (no trailing newline if empty)."""
    lines = [json.dumps([e.ts, e.type, e.text]) for e in events]
    return "\n".join(lines) + ("\n" if lines else "")


def _preprocess(script_text: str, directive_prefix: str = "SC") -> str:
    """Rewrite script lines using directive pre-phase before shell execution."""
    directives = build_directives(directive_prefix)
    lines = script_text.splitlines(keepends=True)
    for d in directives:
        lines = d.pre(lines)
    return "".join(lines)


def _postprocess(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> str:
    """Convert raw .log text to JSONL .sc body (no header line)."""
    directives = build_directives(directive_prefix, trace_prefix)
    events = _parse_raw(raw_text, trace_prefix, directive_prefix)
    for d in directives:
        events = d.post(events)
    return _serialise(events)


def record(
    script_path: str | Path,
    sc_path: str | Path,
    config: ScriptcastConfig,
    shell: str,
) -> int:
    """Run script_path in shell with tracing, write cleaned output to sc_path.

    Returns the shell exit code. Warns (does not raise) on non-zero exit.
    """
    script_path = Path(script_path)
    sc_path = Path(sc_path)
    adapter = get_adapter(shell)

    preamble = adapter.tracing_preamble(config.trace_prefix)

    script_content = script_path.read_text()
    if script_content.startswith("#!"):
        _, _, script_content = script_content.partition("\n")

    script_content = _preprocess(script_content, config.directive_prefix)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, dir=tempfile.gettempdir()
    )
    try:
        tmp.write(preamble)
        tmp.write(script_content)
        tmp.flush()
        tmp.close()

        proc = subprocess.Popen(
            [shell, tmp.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=script_path.parent,
        )
        raw_lines: list[str] = []
        for line in proc.stdout:  # type: ignore[union-attr]
            ts = time.time()
            raw_lines.append(f"{ts:.3f} {line}")
        proc.wait()

        raw_text = "".join(raw_lines)
        clean_text = _postprocess(raw_text, config.trace_prefix, config.directive_prefix)

        header = json.dumps({
            "version": 1,
            "shell": adapter.name,
            "width": config.width,
            "height": config.height,
            "directive-prefix": config.directive_prefix,
            "pipeline-version": 2,
        })
        sc_path.write_text(header + "\n" + clean_text)

        if proc.returncode != 0:
            warnings.warn(
                f"Script exited with non-zero status {proc.returncode}. "
                f".sc file written anyway.",
                UserWarning,
            )
        return proc.returncode
    finally:
        os.unlink(tmp.name)
