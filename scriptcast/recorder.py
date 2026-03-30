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
            _send_re = re.compile(r"""^\s*send\s+(['"])(.*?)\1\s*$""")
            for bl in body:
                sm = _send_re.match(bl.rstrip("\n\r"))
                if sm:
                    input_text = sm.group(2)
                    if input_text.endswith("\\r"):
                        input_text = input_text[:-2]
                    new_body.append(f'send_user ": {directive_prefix} mark input {input_text}\\n"\n')
                elif re.match(r"^\s*send\s+", bl):
                    new_body.append(f'send_user ": {directive_prefix} mark input\\n"\n')
                new_body.append(bl)
            result.append(f"expect <<'{delim}'\n")
            result.extend(new_body)
            result.append(closing)
            i += 1
            continue

        result.append(lines[i])
        i += 1

    return "".join(result)


def _compile_sed_filter(expr: str):
    """Compile a sed s/pattern/replacement/flags expression to a Python callable."""
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


def _postprocess(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> str:
    """Convert raw .log text to JSONL .sc body (no header line)."""
    dp = directive_prefix
    tp = trace_prefix
    mark_input_re = re.compile(rf"(.*?): {re.escape(dp)} mark input\s*(.*?)$")

    lines = raw_text.splitlines()
    result: list[str] = []
    skip_next = False
    paused = False
    filters: list = []
    pending_echo: str | None = None  # for trace-based mark input (skip pty echo)
    pending_input_marker: str | None = None  # for inline mark input (delay input event)
    ts = 0.0

    def apply_filters(text: str) -> str:
        for f in filters:
            text = f(text)
        return text

    for line in lines:
        ts_str, _, content = line.partition(" ")
        try:
            ts = float(ts_str)
        except ValueError:
            continue
        content = content.rstrip("\n\r")

        if skip_next:
            skip_next = False
            # "spawn <cmd>" line from expect — emit as a cmd event
            if not paused and content.startswith("spawn "):
                spawn_cmd = content[len("spawn "):]
                result.append(json.dumps([ts, "cmd", spawn_cmd]))
            continue

        trace_marker = f"{tp} "
        if content.startswith(trace_marker):
            rest = content[len(trace_marker):]

            if rest.startswith("source ") or rest.startswith(". "):
                continue
            if rest == "expect" or rest.startswith("expect "):
                skip_next = True  # skip subsequent "spawn ..." line
                continue

            sc_prefix = f": {dp} "
            if rest.startswith(sc_prefix):
                parts = rest[len(sc_prefix):].split()
                if not parts:
                    continue
                name = parts[0].lower()
                args = parts[1:]

                if name == "mark" and args[:1] == ["mock"]:
                    skip_next = True
                    continue
                if name == "mark" and args[:1] == ["input"]:
                    if not paused:
                        input_text = " ".join(args[1:])
                        result.append(json.dumps([ts, "input", input_text]))
                        pending_echo = input_text
                    continue
                if name == "record":
                    if args[:1] == ["pause"]:
                        paused = True
                    elif args[:1] == ["resume"]:
                        paused = False
                    continue
                if name == "filter":
                    if args[:1] == ["sed"]:
                        try:
                            filters = [_compile_sed_filter(" ".join(args[1:]))]
                        except ValueError:
                            filters = []
                    continue
                if name == "filter-add":
                    if args[:1] == ["sed"]:
                        try:
                            filters.append(_compile_sed_filter(" ".join(args[1:])))
                        except ValueError:
                            pass
                    continue

                if not paused:
                    result.append(json.dumps([ts, "directive", " ".join([name] + args)]))
                continue

            if not paused:
                result.append(json.dumps([ts, "cmd", rest]))

        else:
            m = mark_input_re.match(content)
            if m:
                prefix = m.group(1)  # preserve trailing space (e.g. "mysql> ")
                input_text = m.group(2).strip()
                if not paused:
                    if prefix.strip():
                        result.append(json.dumps([ts, "output", apply_filters(prefix)]))
                    # Delay input event: wait to see if next line is a pty echo
                    pending_input_marker = input_text
                continue
            if not paused:
                if pending_input_marker is not None:
                    marker = pending_input_marker
                    pending_input_marker = None
                    if content.rstrip("\r") == marker:
                        # pty echo found — use echo text as input value, skip line
                        result.append(json.dumps([ts, "input", marker]))
                        continue
                    else:
                        # no pty echo (silent/password) — emit silent input
                        result.append(json.dumps([ts, "input", ""]))
                        if not content.rstrip("\r"):
                            continue  # blank line is send_user \n artifact, not real output
                        # fall through to emit non-blank content as output
                elif pending_echo is not None:
                    if content.rstrip("\r") == pending_echo:
                        pending_echo = None
                        continue
                    pending_echo = None
                result.append(json.dumps([ts, "output", apply_filters(content)]))

    # Flush any pending input at end of stream (silent — no pty echo found)
    if pending_input_marker is not None and not paused:
        result.append(json.dumps([ts, "input", ""]))

    return "\n".join(result) + ("\n" if result else "")


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
            cwd=script_path.parent,
        )
        raw_lines: list[str] = []
        for line in proc.stdout:
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
