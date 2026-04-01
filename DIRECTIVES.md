# Writing Directives

Directives are the extension point in scriptcast. Each directive is a Python
class that participates in one or more of the three pipeline phases:

| Phase | Method | When it runs |
|-------|--------|-------------|
| Pre | `pre(queue)` | Before the shell script is executed — rewrites script lines |
| Post | `post(queue)` | After execution — transforms raw xtrace lines into JSONL events |
| Gen | `gen(event, queue, active, cursor)` | During cast generation — emits asciinema cast lines |

A directive can implement any combination of these phases by overriding the
corresponding method. The base `Directive` class provides no-op defaults for all
three, so you only override what you need.

## The Directive Base Class

```python
from scriptcast.directives import Directive

class MyDirective(Directive):
    priority: int = 50        # lower = runs earlier in the chain
    handles: str | None = None  # gen phase only: directive name in .sc events
```

### priority

Directives are sorted by `priority` before being placed in the processing chain.
Lower values run first. Core directive priorities:

| Directive | Priority | Notes |
|-----------|----------|-------|
| RecordDirective | 10 | Must absorb pause/resume before anything else |
| MockDirective | 20 | Must absorb mock markers before expect or sc catch them |
| ExpectDirective | 30 | Owns all lines in an expect session; must precede filter |
| FilterDirective | 40 | Applies to output lines after expect releases them |
| CommentDirective | 45 | Must precede ScDirective (catch-all) |
| SetDirective | 50 | Gen phase only |
| SleepDirective | 50 | Gen phase only |
| ScDirective | 99 | Catch-all for any remaining `: SC` line — always last |

Pick a priority between 50 and 98 for most new directives.

### handles

Used in the gen phase only. Set `handles = "myname"` and your directive's `gen()`
method will be called when a `directive` event with text `myname ...` appears in the
`.sc` file. If `handles` is `None`, `gen()` is never called automatically.

## Phase Details

### pre(queue: deque[str]) → list[str] | None

Called for each line of the script before it is run. The queue contains the
remaining unprocessed script lines.

- **Return None** if this line is not for you — the next directive gets a chance.
- **Return a list of strings** (replacement lines) to consume from the queue and
  substitute. You are responsible for `queue.popleft()` on lines you consume.

```python
def pre(self, queue):
    if not queue[0].startswith(f": {self.dp} mything"):
        return None
    queue.popleft()
    return ["echo 'replaced'\n"]
```

### post(queue: deque[tuple[float, str]]) → list[str] | None

Called for each (timestamp, content) item in the raw xtrace output. The queue
contains remaining unprocessed items.

- **Return None** if this item is not for you.
- **Return a list of JSONL strings** (or `[]` to consume without emitting).
- Use `json.dumps([ts, "cmd"|"output"|"input"|"directive", text])` to produce events.

```python
import json

def post(self, queue):
    ts, content = queue[0]
    if content != f"{self.tp} : {self.dp} mything":
        return None
    queue.popleft()
    return [json.dumps([ts, "directive", "mything"])]
```

### gen(event, queue, active, cursor) → tuple[float, list[str]]

Called during cast generation when a `directive` event matches `self.handles`.

- `event` — `(timestamp: float, "directive", text: str)`
- `queue` — remaining events (you may peek/consume ahead)
- `active` — current `ScriptcastConfig` (mutable — you can change timing settings)
- `cursor` — current time position in the cast (seconds)
- **Return** `(updated_cursor, list_of_cast_json_lines)`

```python
import json

class MySleepDirective(Directive):
    handles = "mysleep"

    def gen(self, event, queue, active, cursor):
        _, _, text = event
        parts = text.split()
        if len(parts) >= 2:
            cursor += int(parts[1]) / 1000.0
        return cursor, []
```

## Registering a Third-Party Directive

In your package's `pyproject.toml`:

```toml
[project.entry-points."scriptcast.directives"]
my-directive = "mypkg.directives:MyDirective"
```

After `pip install` your package alongside scriptcast, your directive is
automatically loaded and sorted into the processing chain by priority.

## Worked Example: SC pause directive

This adds a `SC pause <ms>` recorder directive that inserts a `sleep` event
into the `.sc` file, causing the generator to pause for the given milliseconds.

```python
# mypkg/directives.py
import json
import re
from scriptcast.directives import Directive


class PauseDirective(Directive):
    """SC pause <ms> — insert a pause into the cast.

    Script syntax:  : SC pause 500
    Records as:     [ts, "directive", "sleep 500"]
    """
    priority = 48  # between CommentDirective (45) and ScDirective (99)

    def __init__(self, dp="SC", tp="+"):
        super().__init__(dp, tp)
        self._re = re.compile(rf"^{re.escape(tp)} : {re.escape(dp)} pause (\d+)$")

    def post(self, queue):
        ts, content = queue[0]
        m = self._re.match(content)
        if not m:
            return None
        queue.popleft()
        ms = m.group(1)
        return [json.dumps([ts, "directive", f"sleep {ms}"])]
```

```toml
# mypkg/pyproject.toml
[project.entry-points."scriptcast.directives"]
pause = "mypkg.directives:PauseDirective"
```
