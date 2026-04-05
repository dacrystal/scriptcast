# scriptcast/registry.py
from __future__ import annotations

import warnings
from importlib.metadata import entry_points

from .directives import (
    CommentDirective,
    Directive,
    ExpectDirective,
    FilterDirective,
    MockDirective,
    RecordDirective,
    ScEvent,
    SetDirective,
    SleepDirective,
)


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
