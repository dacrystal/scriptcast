import json
import re
import shlex
import subprocess
import warnings
from collections import deque
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Iterator, Literal

from .config import ScriptcastConfig

EventType = Literal["cmd", "out", "dir"]


def _iter_heredoc(
    lines: list[str],
    pattern: re.Pattern[str],
) -> Iterator[str | tuple[re.Match[str], list[str], str]]:
    """Iterate lines, yielding either pass-through strings or heredoc block tuples.

    For each line that matches *pattern*, collects the body lines up to the
    heredoc delimiter and yields ``(match, body_lines, closing_line)``.
    Non-matching lines are yielded as plain strings.
    """
    i = 0
    while i < len(lines):
        m = pattern.match(lines[i].rstrip("\n\r"))
        if not m:
            yield lines[i]
            i += 1
            continue
        delim = m.group(3)
        i += 1
        body: list[str] = []
        while i < len(lines) and lines[i].rstrip("\n\r") != delim:
            body.append(lines[i])
            i += 1
        closing = lines[i] if i < len(lines) else delim + "\n"
        i += 1
        yield m, body, closing


@dataclass(frozen=True)
class ScEvent:
    ts: float
    type: EventType
    text: str


class Directive:
    priority: int = 50
    handles: str | None = None  # gen-phase: directive name matched in .sc events

    def __init__(self, dp: str = "SC", tp: str = "+"):
        self.dp = dp
        self.tp = tp

    def pre(self, lines: list[str]) -> list[str]:
        """Pre-phase: rewrite script lines before shell execution.

        Receive the full list of script lines, return a transformed list.
        Lines not recognised by this directive must be passed through unchanged.
        """
        return lines

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        """Post-phase: transform ScEvents.

        Receive the full list, return a transformed list.
        Events not recognised by this directive must be passed through unchanged.
        """
        return events

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: ScriptcastConfig,
        cursor: float,
    ) -> tuple[float, list[str]]:
        """Gen-phase: emit cast lines for a directive event."""
        return cursor, []


class MockDirective(Directive):
    priority = 20

    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._mock_re = re.compile(
            rf"^:\s+{re.escape(dp)}\s+mock\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$"
        )

    def pre(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for item in _iter_heredoc(lines, self._mock_re):
            if isinstance(item, str):
                out.append(item)
                continue
            m, body, closing = item
            cmd_args = m.group(1).strip()
            quote = m.group(2)
            delim = m.group(3)
            out.extend([
                f"(: {self.dp} mark mock; set +x; echo + {cmd_args}; cat) <<{quote}{delim}{quote}\n",
                *body,
                closing,
            ])
        return out

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        out: list[ScEvent] = []
        i = 0
        while i < len(events):
            e = events[i]
            if e.type == "dir" and e.text == "mark mock":
                i += 1
                # drop following "set +x" cmd event if present
                if i < len(events) and events[i].type == "cmd" and events[i].text == "set +x":
                    i += 1
            else:
                out.append(e)
                i += 1
        return out


class ExpectDirective(Directive):
    priority = 30
    handles = "expect-input"

    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._expect_re = re.compile(
            rf"^:\s+{re.escape(dp)}\s+expect\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$"
        )
        self._send_re = re.compile(r"""^\s*send\s+(['"])(.*?)\1\s*$""")
        self._mark_input_re = re.compile(
            rf"(.*?): {re.escape(dp)} mark input\s*(.*)$"
        )

    def pre(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for item in _iter_heredoc(lines, self._expect_re):
            if isinstance(item, str):
                out.append(item)
                continue
            m, body, closing = item
            cmd_args = m.group(1).strip()
            delim = m.group(3)
            new_body: list[str] = [f"spawn {cmd_args}\n"]
            for bl in body:
                sm = self._send_re.match(bl.rstrip("\n\r"))
                if sm:
                    input_text = sm.group(2)
                    if input_text.endswith("\\r"):
                        input_text = input_text[:-2]
                    new_body.append(
                        f'send_user ": {self.dp} mark input {input_text}\\n"\n'
                    )
                elif re.match(r"^\s*send\s+", bl):
                    new_body.append(f'send_user ": {self.dp} mark input\\n"\n')
                new_body.append(bl)
            out.extend([
                f": {self.dp} mark expect {cmd_args}\n",
                f"expect <<'{delim}'\n",
                *new_body,
                closing,
            ])
        return out

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        out: list[ScEvent] = []
        i = 0
        while i < len(events):
            e = events[i]
            # Pattern 1: SC expect directive marker
            if e.type == "dir" and e.text.startswith("mark expect "):
                cmd = e.text[len("mark expect "):].strip()
                out.append(ScEvent(e.ts, "cmd", cmd))
                i += 1
                i, session_events = self._consume_session(events, i)
                out.extend(session_events)
            # Pattern 2: raw expect call (not via SC expect directive)
            elif e.type == "cmd" and (e.text == "expect" or e.text.startswith("expect ")):
                i += 1
                if i < len(events) and events[i].type == "out" and events[i].text.startswith("spawn "):
                    cmd = events[i].text[len("spawn "):]
                    out.append(ScEvent(e.ts, "cmd", cmd))
                    i += 1
                i, session_events = self._consume_session(events, i)
                out.extend(session_events)
            else:
                out.append(e)
                i += 1
        return out

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: ScriptcastConfig,
        cursor: float,
    ) -> tuple[float, list[str]]:
        _, _, text = event
        # text is "expect-input <input_text>" or just "expect-input"
        parts = text.split(maxsplit=1)
        input_text = parts[1] if len(parts) > 1 else ""
        lines: list[str] = []
        cursor += active.input_wait / 1000.0
        for char in input_text:
            cursor += active.type_speed / 1000.0
            lines.append(json.dumps([round(cursor, 6), "o", char]))
            if char == " ":
                cursor += active.effective_word_pause_s
        lines.append(json.dumps([round(cursor, 6), "o", "\r\n"]))
        return cursor, lines

    def _consume_session(
        self, events: list[ScEvent], i: int
    ) -> tuple[int, list[ScEvent]]:
        session: list[ScEvent] = []
        while i < len(events):
            e = events[i]
            # Terminator: outer shell cmd or SC directive
            if e.type == "cmd":
                # Inner expect calls within the session — skip
                if e.text == "expect" or e.text.startswith("expect "):
                    i += 1
                    continue
                break
            if e.type == "dir":
                break
            # Check for mark input pattern in out events
            mi = self._mark_input_re.match(e.text)
            if mi:
                prefix_out = mi.group(1)
                input_text = mi.group(2).strip()
                if prefix_out.strip():
                    session.append(ScEvent(e.ts, "out", prefix_out))
                i += 1
                # Check for PTY echo on next line
                if i < len(events) and events[i].type == "out":
                    next_e = events[i]
                    if next_e.text.rstrip("\r\n") == input_text:
                        i += 1  # strip PTY echo
                        session.append(ScEvent(e.ts, "dir", f"expect-input {input_text}"))
                    else:
                        session.append(ScEvent(e.ts, "dir", f"expect-input {input_text}"))
                else:
                    session.append(ScEvent(e.ts, "dir", f"expect-input {input_text}"))
                continue
            # Skip spawn line
            if e.text.startswith("spawn "):
                i += 1
                continue
            session.append(ScEvent(e.ts, "out", e.text))
            i += 1
        return i, session


class FilterDirective(Directive):
    priority = 40

    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._filters: list[list[str]] = []

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        out: list[ScEvent] = []
        for e in events:
            if e.type == "dir" and e.text.startswith("filter "):
                argv = shlex.split(e.text[len("filter "):])
                if argv:
                    self._filters = [argv]
                # consumed — not emitted
            elif e.type == "dir" and e.text.startswith("filter-add "):
                argv = shlex.split(e.text[len("filter-add "):])
                if argv:
                    self._filters.append(argv)
                # consumed — not emitted
            elif e.type in ("out", "cmd"):
                out.append(ScEvent(e.ts, e.type, self.apply(e.text)))
            else:
                out.append(e)
        return out

    def apply(self, text: str) -> str:
        # Separate terminator so filters operate on content only
        if text.endswith('\r\n'):
            term, body = '\r\n', text[:-2]
        elif text.endswith('\n'):
            term, body = '\n', text[:-1]
        elif text.endswith('\r'):
            term, body = '\r', text[:-1]
        else:
            term, body = '', text
        for argv in self._filters:
            try:
                result = subprocess.run(argv, input=body, capture_output=True, text=True)
                body = result.stdout.rstrip('\n')
            except OSError:
                body = ''
        return body + term


class RecordDirective(Directive):
    priority = 10

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        out: list[ScEvent] = []
        i = 0
        while i < len(events):
            e = events[i]
            if e.type == "dir" and e.text == "record pause":
                i += 1
                while i < len(events):
                    if events[i].type == "dir" and events[i].text == "record resume":
                        i += 1
                        break
                    i += 1
            else:
                out.append(e)
                i += 1
        return out


class CommentDirective(Directive):
    """Converts `: SC '\\' comment` directive events to cmd events with # comment.

    Script syntax: `: SC '\\' This is a comment`
    After _parse_raw strips the prefix, dir event text is: `'\\' This is a comment`
    Emits: `ScEvent(ts, "cmd", "# This is a comment")`
    """
    priority = 45

    def post(self, events: list[ScEvent]) -> list[ScEvent]:
        out: list[ScEvent] = []
        for e in events:
            if e.type == "dir" and e.text.startswith("'\\\' "):
                out.append(ScEvent(e.ts, "cmd", f"# {e.text[4:]}"))
            elif e.type == "dir" and e.text == "'\\\'":
                out.append(ScEvent(e.ts, "cmd", "#"))
            else:
                out.append(e)
        return out


class SetDirective(Directive):
    priority = 50  # gen-only; ordering relative to SleepDirective is irrelevant
    handles = "set"

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: ScriptcastConfig,
        cursor: float,
    ) -> tuple[float, list[str]]:
        _, _, text = event
        parts = shlex.split(text)
        args = parts[1:]
        if len(args) >= 2:
            active.apply("set", args)
        return cursor, []


class SleepDirective(Directive):
    priority = 50
    handles = "sleep"

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: ScriptcastConfig,
        cursor: float,
    ) -> tuple[float, list[str]]:
        _, _, text = event
        parts = text.split()
        if len(parts) >= 2:
            cursor += int(parts[1]) / 1000.0
        return cursor, []


def build_directives(dp: str = "SC", tp: str = "+") -> list[Directive]:
    """Build the full sorted directive list for the given prefix settings."""
    core: list[Directive] = [
        RecordDirective(dp, tp),
        MockDirective(dp, tp),
        ExpectDirective(dp, tp),
        FilterDirective(dp, tp),
        CommentDirective(dp, tp),
        SetDirective(dp, tp),
        SleepDirective(dp, tp),
    ]

    eps = entry_points(group="scriptcast.directives")
    plugins: list[Directive] = []
    for ep in eps:
        try:
            plugins.append(ep.load()(dp, tp))
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to load scriptcast directive plugin {ep.name!r}: {exc}",
                UserWarning,
                stacklevel=2,
            )

    return sorted(core + plugins, key=lambda d: d.priority)
