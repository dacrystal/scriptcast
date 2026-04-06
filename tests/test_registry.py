import shutil

import pytest

from scriptcast.directives import (
    CommentDirective,
    ExpectDirective,
    FilterDirective,
    HelpersDirective,
    MockDirective,
    RecordDirective,
    SetDirective,
    SleepDirective,
    build_directives,
)


def test_build_directives_returns_list():
    result = build_directives()
    assert isinstance(result, list)
    assert len(result) > 0


def test_build_directives_sorted_by_priority():
    result = build_directives()
    priorities = [d.priority for d in result]
    assert priorities == sorted(priorities)


def test_build_directives_contains_all_core():
    result = build_directives()
    types = {type(d) for d in result}
    assert HelpersDirective in types
    assert RecordDirective in types
    assert MockDirective in types
    assert ExpectDirective in types
    assert FilterDirective in types
    assert CommentDirective in types
    assert SetDirective in types
    assert SleepDirective in types


def test_expect_before_filter():
    result = build_directives()
    types = [type(d) for d in result]
    assert types.index(ExpectDirective) < types.index(FilterDirective)


def test_helpers_before_record():
    result = build_directives()
    types = [type(d) for d in result]
    assert types.index(HelpersDirective) < types.index(RecordDirective)


def test_build_directives_dp_tp_propagated():
    result = build_directives(dp="DEMO", tp=">>")
    for d in result:
        assert d.dp == "DEMO"
        assert d.tp == ">>"
