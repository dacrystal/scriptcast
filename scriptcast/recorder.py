# scriptcast/recorder.py
from __future__ import annotations
import os
import re
import subprocess
import tempfile
import time
import warnings
from pathlib import Path
from typing import Union

from .config import ScriptcastConfig
from .shell import get_adapter


def _preprocess(script_text: str, directive_prefix: str = "SC") -> str:
    """Rewrite SC mock/expect directives to executable shell before recording."""
    dp = re.escape(directive_prefix)
    mock_re = re.compile(rf"^:\s+{dp}\s+mock\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$")
    expect_re = re.compile(rf"^:\s+{dp}\s+expect\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$")

    lines = script_text.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].rstrip("\n\r")

        m = mock_re.match(stripped)
        if m:
            cmd_args = m.group(1).strip()
            delim = m.group(3)
            i += 1
            body: list[str] = []
            while i < len(lines) and lines[i].rstrip("\n\r") != delim:
                body.append(lines[i])
                i += 1
            closing = lines[i] if i < len(lines) else delim + "\n"
            result.append(
                f"(: {directive_prefix} mark mock; set +x; echo + {cmd_args}; cat) <<'{delim}'\n"
            )
            result.extend(body)
            result.append(closing)
            i += 1
            continue

        m = expect_re.match(stripped)
        if m:
            cmd_args = m.group(1).strip()
            delim = m.group(3)
            i += 1
            body = []
            while i < len(lines) and lines[i].rstrip("\n\r") != delim:
                body.append(lines[i])
                i += 1
            closing = lines[i] if i < len(lines) else delim + "\n"
            new_body: list[str] = [f"spawn {cmd_args}\n"]
            for bl in body:
                if re.match(r"^\s*send\s+", bl):
                    new_body.append(f'send_user ": {directive_prefix} mark input"\n')
                new_body.append(bl)
            result.append(f"expect <<'{delim}'\n")
            result.extend(new_body)
            result.append(closing)
            i += 1
            continue

        result.append(lines[i])
        i += 1

    return "".join(result)


def _postprocess(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> str:
    """Strip recorder artifacts from raw .sc output before writing final .sc file."""
    mock_marker = f"{trace_prefix} : {directive_prefix} mark mock"
    expect_prefix = f"{trace_prefix} expect"

    lines = raw_text.splitlines(keepends=True)
    result: list[str] = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        # Strip timestamp → content
        _, _, content = line.partition(" ")
        content_stripped = content.rstrip("\n\r")

        if content_stripped == mock_marker:
            skip_next = True  # next line is the "+ set +x" trace
            continue

        if content_stripped == expect_prefix or content_stripped.startswith(f"{expect_prefix} "):
            continue

        result.append(line)
    return "".join(result)


def record(
    script_path: Union[str, Path],
    sc_path: Union[str, Path],
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
        )
        raw_lines: list[str] = []
        for line in proc.stdout:
            ts = time.time()
            raw_lines.append(f"{ts:.3f} {line}")
        proc.wait()

        raw_text = "".join(raw_lines)
        clean_text = _postprocess(raw_text, config.trace_prefix, config.directive_prefix)

        sc_path.write_text(
            f"#shell={adapter.name}\n"
            f"#trace-prefix={config.trace_prefix}\n"
            f"#directive-prefix={config.directive_prefix}\n"
            + clean_text
        )

        if proc.returncode != 0:
            warnings.warn(
                f"Script exited with non-zero status {proc.returncode}. "
                f".sc file written anyway.",
                UserWarning,
            )
        return proc.returncode
    finally:
        os.unlink(tmp.name)
