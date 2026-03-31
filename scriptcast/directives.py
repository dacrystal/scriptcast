from __future__ import annotations
import json
import re
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ScriptcastConfig


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


class Directive:
    def __init__(self, dp: str = "SC", tp: str = "+"):
        self.dp = dp
        self.tp = tp

    def pre(self, queue: deque[str]) -> list[str] | None:
        """Pre-phase. Peek queue[0]; return None if not this directive's line."""
        return None

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        """Post-phase. Peek queue[0]; return None if not this directive's item."""
        return None

    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: "ScriptcastConfig",
        cursor: float,
    ) -> tuple[float, list[str]]:
        """Gen-phase: emit cast lines for a directive event. Default: no output."""
        return cursor, []


class RecorderDirective(Directive):
    """Directive that participates in pre and/or post phases."""


class GeneratorDirective(Directive):
    """Directive that participates in the gen phase."""


class MockDirective(RecorderDirective):
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
        delim = m.group(3)
        body: list[str] = []
        while queue and queue[0].rstrip("\n\r") != delim:
            body.append(queue.popleft())
        closing = queue.popleft() if queue else delim + "\n"
        return [
            # Always use single quotes for the heredoc delimiter - mock body is static data,
            # so variable expansion doesn't apply regardless of original quote style
            f"(: {self.dp} mark mock; set +x; echo + {cmd_args}; cat) <<'{delim}'\n",
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


class ExpectDirective(RecorderDirective):
    def __init__(self, dp: str = "SC", tp: str = "+", filter_apply=None):
        super().__init__(dp, tp)
        self._filter_apply = filter_apply or (lambda t: t)
        self._expect_re = re.compile(
            rf"^:\s+{re.escape(dp)}\s+expect\s+(.+?)\s*<<(['\"]?)(\w+)\2\s*$"
        )
        self._send_re = re.compile(r"""^\s*send\s+(['"])(.*?)\1\s*$""")
        self._mark_input_re = re.compile(
            rf"(.*?): {re.escape(dp)} mark input\s*(.*)$"
        )

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
                mi = self._mark_input_re.match(rest)
                if mi:
                    queue.popleft()
                    self._consume_mark_input(queue, events, line_ts, mi)
                    continue
                if rest.startswith(f"{self.tp} "):
                    return events
                queue.popleft()
                events.append(json.dumps([line_ts, "output", self._filter_apply(rest)]))
            return events

        prefix_str = f"{self.tp} : {self.dp} mark expect "
        if not content.startswith(prefix_str):
            return None
        queue.popleft()
        cmd = content[len(prefix_str):].strip()

        events: list[str] = []
        events.append(json.dumps([ts, "cmd", cmd]))

        while queue:
            line_ts, rest = queue[0]  # peek

            # mark input FIRST — before the termination check.
            # Lines like ": SC mark input text" (empty output prefix) would otherwise
            # match the ": SC ..." termination check and escape the session.
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
            events.append(json.dumps([line_ts, "output", self._filter_apply(rest)]))

        return events

    def _consume_mark_input(
        self,
        queue: deque[tuple[float, str]],
        events: list[str],
        line_ts: float,
        mi,
    ) -> None:
        """Pop and process a mark-input match from the queue into events."""
        prefix_out = mi.group(1)
        input_text = mi.group(2).strip()
        if prefix_out.strip():
            events.append(json.dumps([line_ts, "output", self._filter_apply(prefix_out)]))
        if queue:
            next_ts, next_rest = queue[0]
            if next_rest.rstrip("\r") == input_text:
                queue.popleft()
                events.append(json.dumps([line_ts, "input", input_text]))
            else:
                events.append(json.dumps([line_ts, "input", ""]))
                if not next_rest.rstrip("\r"):
                    queue.popleft()  # blank send_user artifact
        else:
            events.append(json.dumps([line_ts, "input", ""]))


class FilterDirective(RecorderDirective):
    def __init__(self, dp: str = "SC", tp: str = "+"):
        super().__init__(dp, tp)
        self._filters: list = []

    def post(self, queue: deque[tuple[float, str]]) -> list[str] | None:
        ts, content = queue[0]
        sc_filter = f"{self.tp} : {self.dp} filter "
        sc_filter_add = f"{self.tp} : {self.dp} filter-add "
        if content.startswith(sc_filter):
            name, rest = "filter", content[len(sc_filter):]
        elif content.startswith(sc_filter_add):
            name, rest = "filter-add", content[len(sc_filter_add):]
        else:
            # Plain output line — apply filter transform in-place, let else-branch emit it
            if not content.startswith(f"{self.tp} "):
                queue[0] = (ts, self.apply(content))
            return None
        queue.popleft()
        parts = rest.split()
        if parts[:1] == ["sed"]:
            try:
                fn = _compile_sed_filter(" ".join(parts[1:]))
            except ValueError:
                return []
            if name == "filter":
                self._filters = [fn]
            else:
                self._filters.append(fn)
        return []

    def apply(self, text: str) -> str:
        for fn in self._filters:
            text = fn(text)
        return text


class RecordDirective(RecorderDirective):
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


class ScDirective(RecorderDirective):
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


class SetDirective(GeneratorDirective):
    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: "ScriptcastConfig",
        cursor: float,
    ) -> tuple[float, list[str]]:
        _, _, text = event
        parts = text.split()
        # parts: ["set", key, value, ...]
        args = parts[1:]
        if len(args) >= 2:
            active.apply("set", args)
        return cursor, []


class SleepDirective(GeneratorDirective):
    def gen(
        self,
        event: tuple,
        queue: deque[tuple],
        active: "ScriptcastConfig",
        cursor: float,
    ) -> tuple[float, list[str]]:
        _, _, text = event
        parts = text.split()
        # parts: ["sleep", ms]
        if len(parts) >= 2:
            cursor += int(parts[1]) / 1000.0
        return cursor, []
