import shutil

import pytest

from scriptcast.directives import (
    CommentDirective,
    ExpectDirective,
    FilterDirective,
    MockDirective,
    RecordDirective,
    ScDirective,
    SetDirective,
    SleepDirective,
)
from scriptcast.registry import build_directives


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
    assert RecordDirective in types
    assert MockDirective in types
    assert ExpectDirective in types
    assert FilterDirective in types
    assert CommentDirective in types
    assert ScDirective in types
    assert SetDirective in types
    assert SleepDirective in types


def test_record_directive_before_sc_directive():
    result = build_directives()
    types = [type(d) for d in result]
    assert types.index(RecordDirective) < types.index(ScDirective)


def test_expect_before_filter():
    result = build_directives()
    types = [type(d) for d in result]
    assert types.index(ExpectDirective) < types.index(FilterDirective)


@pytest.mark.skipif(shutil.which("tr") is None, reason="tr not available")
def test_expect_directive_has_filter_apply_wired():
    """ExpectDirective._filter_d should be the shared FilterDirective instance."""
    result = build_directives()
    filter_d = next(d for d in result if isinstance(d, FilterDirective))
    expect_d = next(d for d in result if isinstance(d, ExpectDirective))
    # Set a filter that upper-cases input
    filter_d._filters = [["tr", "a-z", "A-Z"]]
    assert expect_d._apply_filter("hello") == "HELLO"


def test_build_directives_dp_tp_propagated():
    result = build_directives(dp="DEMO", tp=">>")
    for d in result:
        assert d.dp == "DEMO"
        assert d.tp == ">>"
