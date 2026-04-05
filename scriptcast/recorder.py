# scriptcast/recorder.py
import errno
import fcntl
import json
import logging
import os
import pty
import re
import struct
import subprocess
import tempfile
import termios
import time
from pathlib import Path

from .config import ScriptcastConfig
from .directives import ScEvent, build_directives
from .shell import get_adapter

logger = logging.getLogger(__name__)


def _parse_raw(
    raw_text: str,
    trace_prefix: str = "+",
    directive_prefix: str = "SC",
) -> list[ScEvent]:
    """Parse raw xtrace log text into an initial list of ScEvents.

    Each record has the form: "<ts> <content><term>" where <term> is one of
    \\r\\n, \\r, \\n, or empty (last record with no terminator).  The pipe
    reader in record() emits one record per terminator, so bare \\r progress-
    bar updates arrive as their own records.

    Classification rules (per record):
      "+ : SC <rest>"  →  ScEvent(ts, "dir",  rest)   — terminator discarded
      "+ <cmd>"        →  ScEvent(ts, "cmd",  cmd)    — terminator discarded
      "<text>"         →  ScEvent(ts, "out",  text + term)  — verbatim

    Lines with non-float timestamps are skipped.
    """
    sc_prefix = f"{trace_prefix} : {directive_prefix} "
    trace_prefix_sp = f"{trace_prefix} "
    events: list[ScEvent] = []

    # Split on any line terminator, keeping each terminator as a token.
    # re.split with a capturing group gives [c0, t0, c1, t1, ..., cN].
    parts = re.split(r'(\r\n|\r|\n)', raw_text)

    i = 0
    while i < len(parts):
        entry = parts[i]
        term = parts[i + 1] if i + 1 < len(parts) else ''
        i += 2

        if not entry:
            continue
        ts_str, _, content = entry.partition(' ')
        try:
            ts = float(ts_str)
        except ValueError:
            continue

        if content.startswith(sc_prefix):
            events.append(ScEvent(ts, "dir", content[len(sc_prefix):]))
        elif content.startswith(trace_prefix_sp):
            events.append(ScEvent(ts, "cmd", content[len(trace_prefix_sp):]))
        else:
            events.append(ScEvent(ts, "out", content + term))

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
    logger.debug("Recording %s (shell=%s, width=%d, height=%d)", script_path.name, shell, config.width, config.height)

    master_fd = -1
    proc = None
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, dir=tempfile.gettempdir()
    )
    try:
        tmp.write(preamble)
        tmp.write(script_content)
        tmp.flush()
        tmp.close()

        master_fd, slave_fd = pty.openpty()
        try:
            fcntl.ioctl(
                slave_fd, termios.TIOCSWINSZ,
                struct.pack('HHHH', config.height, config.width, 0, 0),
            )
            stdin_fd = os.open('/dev/null', os.O_RDONLY)
            try:
                proc = subprocess.Popen(
                    [shell, tmp.name],
                    stdin=stdin_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=script_path.parent,
                )
            finally:
                os.close(slave_fd)
                os.close(stdin_fd)
        except Exception:
            os.close(master_fd)
            master_fd = -1
            raise

        raw_lines: list[str] = []
        buf = b""
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError as e:
                if e.errno != errno.EIO:
                    raise
                break
            if not chunk:
                break
            buf += chunk
            # Emit one raw-log entry per terminator found in buf.
            while True:
                pos_crlf = buf.find(b'\r\n')
                pos_lf = buf.find(b'\n')
                pos_cr = buf.find(b'\r')
                # bare \r: first \r not at the start of a \r\n pair
                bare_cr = pos_cr >= 0 and (pos_crlf < 0 or pos_cr < pos_crlf)

                candidates: list[tuple[int, int]] = []
                if pos_crlf >= 0:
                    candidates.append((pos_crlf, 2))
                if pos_lf >= 0:
                    candidates.append((pos_lf, 1))
                if bare_cr:
                    candidates.append((pos_cr, 1))

                if not candidates:
                    break

                pos, tlen = min(candidates, key=lambda x: x[0])
                ts = time.time()
                line_str = buf[:pos].decode('utf-8', errors='replace')
                term_str = buf[pos:pos + tlen].decode('utf-8', errors='replace')
                buf = buf[pos + tlen:]
                raw_lines.append(f"{ts:.3f} {line_str}{term_str}")

        # Remaining bytes with no terminator (e.g. a prompt without a newline).
        if buf:
            ts = time.time()
            raw_lines.append(f"{ts:.3f} {buf.decode('utf-8', errors='replace')}")
        os.close(master_fd)
        master_fd = -1   # signal to finally: already closed
        proc.wait()

        logger.debug("PTY capture complete: %d raw lines", len(raw_lines))

        raw_text = "".join(raw_lines)
        clean_text = _postprocess(raw_text, config.trace_prefix, config.directive_prefix)
        logger.debug("Post-processed to %d events", clean_text.count("\n"))

        header = json.dumps({
            "version": 1,
            "shell": adapter.name,
            "width": config.width,
            "height": config.height,
            "directive-prefix": config.directive_prefix,
            "pipeline-version": 3,
        })
        sc_path.write_text(header + "\n" + clean_text)

        if proc.returncode != 0:
            logger.warning("Script exited with non-zero status %d; .sc file written anyway.", proc.returncode)
        return proc.returncode
    finally:
        if master_fd != -1:
            os.close(master_fd)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait()
        os.unlink(tmp.name)
