# scriptcast/recorder.py
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import warnings
from collections import deque
from pathlib import Path

from .config import ScriptcastConfig
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


def _preprocess(script_text: str, directive_prefix: str = "SC") -> str:
    """Rewrite SC mock/expect directives to executable shell before recording."""
    directives = build_directives(directive_prefix)
    queue: deque[str] = deque(script_text.splitlines(keepends=True))
    out: list[str] = []
    while queue:
        for d in directives:
            result = d.pre(queue)
            if result is not None:
                out.extend(result)
                break
        else:
            out.append(queue.popleft())
    return "".join(out)


def _postprocess(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> str:
    """Convert raw .log text to JSONL .sc body (no header line)."""
    tp = trace_prefix
    trace_marker = f"{tp} "

    queue: deque[tuple[float, str]] = deque()
    for raw in raw_text.splitlines():
        ts_str, _, content = raw.partition(" ")
        try:
            ts_val = float(ts_str)
        except ValueError:
            continue
        content = content.rstrip("\n\r")
        sc_directive_prefix = f"{tp} : {directive_prefix} "
        if content.startswith(sc_directive_prefix):
            content = _decode_bash_escapes(content)
        queue.append((ts_val, content))

    directives = build_directives(directive_prefix, trace_prefix)
    out: list[str] = []

    while queue:
        for d in directives:
            result = d.post(queue)
            if result is not None:
                out.extend(result)
                break
        else:
            ts, content = queue.popleft()
            if content.startswith(trace_marker):
                out.append(json.dumps([ts, "cmd", content[len(trace_marker):]]))
            else:
                out.append(json.dumps([ts, "output", content]))

    return "\n".join(out) + ("\n" if out else "")


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
