from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ScriptcastConfig


class Directive:
    priority: int = 50
    handles: str | None = None  # gen-phase: directive name matched in .sc events

    def __init__(self, dp: str = "SC", tp: str = "+"):
        self.dp = dp
        self.tp = tp

    def pre(self, queue: deque[str]) -> list[str] | None:
        """Pre-phase: rewrite script lines before shell execution.

        Peek queue[0]; consume lines and return replacement lines, or return
        None if this directive does not match the current line.
        """
        return None

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        """Post-phase: transform raw xtrace lines into JSONL .sc events.

        Peek queue[0]; consume lines and return JSONL strings, or return
        None if this directive does not match the current line.
        Return [] to consume lines without emitting output.
        """
        return None

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: ScriptcastConfig,
        cursor: float,
    ) -> tuple[float, list[str]]:
        """Gen-phase: emit cast lines for a directive event.

        Called when a 'directive' event is found in the .sc file and this
        directive's `handles` matches the directive name. Return updated
        cursor and list of JSON cast lines.
        """
        return cursor, []


class MockDirective(Directive):
    priority = 20

    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._mock_re = re.compile(
            rf"^:\s+{re.escape(dp)}\s+mock\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$"
        )

    def pre(self, queue: deque[str]) -> list[str] | None:
        m = self._mock_re.match(queue[0].rstrip("\n\r"))
        if not m:
            return None
        queue.popleft()
        cmd_args = m.group(1).strip()
        quote = m.group(2)
        delim = m.group(3)
        body: list[str] = []
        while queue and queue[0].rstrip("\n\r") != delim:
            body.append(queue.popleft())
        closing = queue.popleft() if queue else delim + "\n"
        return [
            f"(: {self.dp} mark mock; set +x; echo + {cmd_args}; cat) <<{quote}{delim}{quote}\n",
            *body,
            closing,
        ]

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        if content != f"{self.tp} : {self.dp} mark mock":
            return None
        queue.popleft()
        if queue:
            queue.popleft()  # drop set +x
        return []


class ExpectDirective(Directive):
    priority = 30

    def __init__(
        self, dp: str = "SC", tp: str = "+", filter_d: FilterDirective | None = None
    ):
        super().__init__(dp, tp)
        self._filter_d = filter_d
        self._expect_re = re.compile(
            rf"^:\s+{re.escape(dp)}\s+expect\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$"
        )
        self._send_re = re.compile(r"""^\s*send\s+(['"])(.*?)\1\s*$""")
        self._mark_input_re = re.compile(
            rf"(.*?): {re.escape(dp)} mark input\s*(.*)$"
        )

    def _apply_filter(self, text: str) -> str:
        return self._filter_d.apply(text) if self._filter_d else text

    def pre(self, queue: deque[str]) -> list[str] | None:
        m = self._expect_re.match(queue[0].rstrip("\n\r"))
        if not m:
            return None
        queue.popleft()
        cmd_args = m.group(1).strip()
        delim = m.group(3)
        body: list[str] = []
        while queue and queue[0].rstrip("\n\r") != delim:
            body.append(queue.popleft())
        closing = queue.popleft() if queue else delim + "\n"
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
        return [
            f": {self.dp} mark expect {cmd_args}\n",
            f"expect <<'{delim}'\n",
            *new_body,
            closing,
        ]

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]

        # Absorb bare "+ expect" trace line (raw expect call, not via SC expect directive)
        if content == f"{self.tp} expect" or content.startswith(f"{self.tp} expect "):
            queue.popleft()
            if not queue:
                return []
            _, spawn_content = queue.popleft()
            if not spawn_content.startswith("spawn "):
                return []
            cmd = spawn_content[len("spawn "):]
            events: list[str] = [json.dumps([ts, "cmd", cmd])]
            while queue:
                line_ts, rest = queue[0]
                # mark input FIRST — before the termination check.
                # Lines like ": SC mark input text" (empty output prefix) would otherwise
                # match the ": SC ..." termination check and escape the session.
                mi = self._mark_input_re.match(rest)
                if mi:
                    queue.popleft()
                    self._consume_mark_input(queue, events, line_ts, mi)
                    continue
                if rest.startswith(f"{self.tp} "):
                    return events
                queue.popleft()
                events.append(json.dumps([line_ts, "output", self._apply_filter(rest)]))
            return events

        prefix_str = f"{self.tp} : {self.dp} mark expect "
        if not content.startswith(prefix_str):
            return None
        queue.popleft()
        cmd = content[len(prefix_str):].strip()

        events = []
        events.append(json.dumps([ts, "cmd", cmd]))

        while queue:
            line_ts, rest = queue[0]

            mi = self._mark_input_re.match(rest)
            if mi:
                queue.popleft()
                self._consume_mark_input(queue, events, line_ts, mi)
                continue

            # "+ expect" trace within session — skip
            if rest == f"{self.tp} expect" or rest.startswith(f"{self.tp} expect "):
                queue.popleft()
                continue

            # Outer shell resumed — leave line in queue and stop
            if rest.startswith(f"{self.tp} ") or rest.startswith(f": {self.dp} "):
                return events

            queue.popleft()
            if rest.startswith("spawn "):
                continue
            events.append(json.dumps([line_ts, "output", self._apply_filter(rest)]))

        return events

    def _consume_mark_input(
        self,
        queue: deque[tuple[float, str]],
        events: list[str],
        line_ts: float,
        mi: re.Match[str],
    ) -> None:
        prefix_out = mi.group(1)
        input_text = mi.group(2).strip()
        if prefix_out.strip():
            events.append(json.dumps([line_ts, "output", self._apply_filter(prefix_out)]))
        if queue:
            next_ts, next_rest = queue[0]
            if next_rest.rstrip("\r") == input_text:
                queue.popleft()
                events.append(json.dumps([line_ts, "input", input_text]))
            else:
                events.append(json.dumps([line_ts, "input", ""]))
                if not next_rest.rstrip("\r"):
                    queue.popleft()
        else:
            events.append(json.dumps([line_ts, "input", ""]))


class FilterDirective(Directive):
    priority = 40

    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._filters: list[list[str]] = []

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        sc_filter = f"{self.tp} : {self.dp} filter "
        sc_filter_add = f"{self.tp} : {self.dp} filter-add "
        if content.startswith(sc_filter):
            name, rest = "filter", content[len(sc_filter):]
        elif content.startswith(sc_filter_add):
            name, rest = "filter-add", content[len(sc_filter_add):]
        else:
            trace_pfx = f"{self.tp} "
            sc_pfx = f"{self.tp} : {self.dp} "
            if content.startswith(sc_pfx):
                pass  # SC directive line — don't filter
            elif content.startswith(trace_pfx):
                # Trace/cmd line: filter the command portion after the trace prefix
                cmd = content[len(trace_pfx):]
                queue[0] = (ts, trace_pfx + self.apply(cmd))
            else:
                queue[0] = (ts, self.apply(content))
            return None
        queue.popleft()
        argv = shlex.split(rest)
        if not argv:
            return []
        if name == "filter":
            self._filters = [argv]
        else:
            self._filters.append(argv)
        return []

    def apply(self, text: str) -> str:
        for argv in self._filters:
            try:
                result = subprocess.run(argv, input=text, capture_output=True, text=True)
                text = result.stdout.rstrip("\n")
            except OSError:
                text = ""
        return text


class RecordDirective(Directive):
    priority = 10

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        if content != f"{self.tp} : {self.dp} record pause":
            return None
        queue.popleft()
        while queue:
            _, c = queue.popleft()
            if c == f"{self.tp} : {self.dp} record resume":
                break
        return []


class ScDirective(Directive):
    priority = 99  # catch-all — must run last

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        prefix = f"{self.tp} : {self.dp} "
        if not content.startswith(prefix):
            return None
        queue.popleft()
        rest = content[len(prefix):].strip()
        if rest:
            return [json.dumps([ts, "directive", rest])]
        return []


class CommentDirective(Directive):
    """Matches `: SC '\\' comment` trace lines and emits [ts, "cmd", "# comment"].

    Script syntax: `: SC '\\' This is a comment`
    Bash traces as: `+ : SC '\\' This is a comment`
    """
    priority = 45  # must precede ScDirective (catch-all)

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        prefix = f"{self.tp} : {self.dp} '\\' "
        bare = f"{self.tp} : {self.dp} '\\'"
        if content.startswith(prefix):
            rest = content[len(prefix):]
            queue.popleft()
            return [json.dumps([ts, "cmd", f"# {rest}"])]
        if content == bare:
            queue.popleft()
            return [json.dumps([ts, "cmd", "#"])]
        return None


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
