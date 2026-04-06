import dataclasses
import json
from collections import deque

import pytest
from scriptcast.config import ScriptcastConfig
from scriptcast.directives import (
    CommentDirective,
    Directive,
    ExpectDirective,
    FilterDirective,
    HelpersDirective,
    MockDirective,
    RecordDirective,
    ScEvent,
    SetDirective,
    SleepDirective,
)


def test_sc_event_fields():
    e = ScEvent(ts=1.0, type="cmd", text="echo hi")
    assert e.ts == 1.0
    assert e.type == "cmd"
    assert e.text == "echo hi"


def test_sc_event_is_frozen():
    e = ScEvent(ts=1.0, type="cmd", text="echo hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.ts = 2.0  # type: ignore[misc]


def test_directive_pre_passthrough():
    d = Directive()
    lines = ["echo hello\n", "exit 0\n"]
    assert d.pre(lines) == lines


def test_directive_post_passthrough():
    d = Directive()
    events = [ScEvent(1.0, "cmd", "echo hi"), ScEvent(1.1, "out", "hi")]
    assert d.post(events) == events


def test_directive_gen_noop():
    d = Directive()
    q = deque()
    cfg = ScriptcastConfig()
    cursor, cast_lines = d.gen((1.0, "dir", "hi"), q, cfg, 0.0)
    assert cursor == 0.0
    assert cast_lines == []


def test_mock_directive_pre_passthrough():
    d = MockDirective()
    lines = ["echo hello\n", "exit 0\n"]
    assert d.pre(lines) == lines


def test_mock_directive_pre_rewrites():
    d = MockDirective()
    lines = [
        ": SC mock deploy <<'EOF'\n",
        "Deploying...\n",
        "OK\n",
        "EOF\n",
        "echo after\n",
    ]
    result = d.pre(lines)
    joined = "".join(result)
    assert "(: SC mark mock; set +x; echo + deploy; cat) <<'EOF'\n" in joined
    assert "Deploying...\n" in joined
    assert "OK\n" in joined
    assert "echo after\n" in joined
    assert ": SC mock" not in joined


def test_mock_directive_pre_custom_prefix():
    d = MockDirective(dp="MY")
    lines = [": MY mock cmd <<'DONE'\n", "output\n", "DONE\n"]
    result = d.pre(lines)
    assert "(: MY mark mock; set +x; echo + cmd; cat) <<'DONE'\n" in "".join(result)


def test_mock_directive_pre_unquoted_heredoc():
    d = MockDirective()
    lines = [": SC mock deploy <<EOF\n", "${GREEN}OK${RESET}\n", "EOF\n"]
    result = d.pre(lines)
    joined = "".join(result)
    assert "(: SC mark mock; set +x; echo + deploy; cat) <<EOF\n" in joined


def test_mock_directive_post_passthrough():
    d = MockDirective()
    events = [ScEvent(1.0, "cmd", "echo hi")]
    assert d.post(events) == events


def test_mock_directive_post_drops_mark_mock_and_set_x():
    d = MockDirective()
    events = [
        ScEvent(1.0, "dir", "mark mock"),
        ScEvent(1.001, "cmd", "set +x"),
        ScEvent(1.002, "cmd", "deploy arg1"),
    ]
    result = d.post(events)
    assert result == [ScEvent(1.002, "cmd", "deploy arg1")]


def test_mock_directive_post_drops_mark_mock_without_set_x():
    d = MockDirective()
    events = [
        ScEvent(1.0, "dir", "mark mock"),
        ScEvent(1.001, "cmd", "deploy arg1"),
    ]
    result = d.post(events)
    assert result == [ScEvent(1.001, "cmd", "deploy arg1")]


def test_expect_directive_pre_passthrough():
    d = ExpectDirective()
    lines = ["echo hello\n", "exit 0\n"]
    assert d.pre(lines) == lines


def test_expect_directive_pre_rewrites():
    d = ExpectDirective()
    lines = [
        ": SC expect mysql <<'EOF'\n",
        'expect "Password:"\n',
        'send "secret\\r"\n',
        "EOF\n",
        "echo after\n",
    ]
    result = d.pre(lines)
    joined = "".join(result)
    assert ": SC mark expect mysql" in joined
    assert "expect <<'EOF'" in joined
    assert "spawn mysql" in joined
    assert 'send_user ": SC mark input secret\\n"' in joined
    assert 'send "secret\\r"' in joined
    assert "echo after\n" in joined
    assert ": SC expect" not in joined


def test_expect_directive_pre_multiple_sends():
    d = ExpectDirective()
    lines = [
        ": SC expect cmd <<'EOF'\n",
        'expect "p1"\n',
        'send "a\\r"\n',
        'expect "p2"\n',
        'send "b\\r"\n',
        "EOF\n",
    ]
    result = d.pre(lines)
    joined = "".join(result)
    assert joined.count('send_user ": SC mark input') == 2
    assert 'send_user ": SC mark input a\\n"' in joined
    assert 'send_user ": SC mark input b\\n"' in joined


def test_expect_directive_pre_no_send():
    d = ExpectDirective()
    lines = [": SC expect app <<'EOF'\n", 'expect "done"\n', "EOF\n"]
    result = d.pre(lines)
    joined = "".join(result)
    assert "spawn app" in joined
    assert "mark input" not in joined


def test_expect_directive_post_passthrough():
    d = ExpectDirective()
    events = [ScEvent(1.0, "cmd", "echo hi"), ScEvent(1.1, "out", "hi")]
    assert d.post(events) == events


def test_expect_directive_post_emits_cmd_from_mark_expect():
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect mysql"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn mysql"),
        ScEvent(1.003, "out", "Password:"),
        ScEvent(1.004, "cmd", "echo hi"),
    ]
    result = d.post(events)
    assert result[0] == ScEvent(1.0, "cmd", "mysql")
    types = [e.type for e in result]
    assert "out" in types
    # Terminator stays in output
    assert ScEvent(1.004, "cmd", "echo hi") in result


def test_expect_directive_post_skips_spawn_line():
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect myapp"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn myapp"),
        ScEvent(1.003, "cmd", "echo done"),
    ]
    result = d.post(events)
    assert not any("spawn" in e.text for e in result)


def test_expect_directive_post_emits_expect_input_for_mark_input():
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect app"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn app"),
        ScEvent(1.003, "out", "Password: : SC mark input secret"),
        ScEvent(1.004, "out", "Welcome"),
        ScEvent(1.005, "cmd", "echo done"),
    ]
    result = d.post(events)
    dir_events = [e for e in result if e.type == "dir"]
    assert any(e.text.startswith("expect-input") for e in dir_events)
    out_events = [e for e in result if e.type == "out"]
    assert any("Password:" in e.text for e in out_events)
    assert any("Welcome" in e.text for e in out_events)


def test_expect_directive_post_strips_pty_echo():
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect app"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn app"),
        ScEvent(1.003, "out", "prompt> : SC mark input show;"),
        ScEvent(1.004, "out", "show;"),   # pty echo — must be stripped
        ScEvent(1.005, "out", "(0 rows)"),
        ScEvent(1.006, "cmd", "echo done"),
    ]
    result = d.post(events)
    out_texts = [e.text for e in result if e.type == "out"]
    assert "show;" not in out_texts
    assert "(0 rows)" in out_texts


def test_expect_directive_post_preserves_cr_lf_from_pty_echo():
    # When the PTY echo includes a trailing \r\n (Enter echo), it must be kept
    # as an out event so the cast shows a newline after the typed input.
    # Bug scenario: "Email: dev@example.comPassword:" (no newline between them).
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect app"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn app"),
        ScEvent(1.003, "out", "Email: : SC mark input dev@example.com"),
        ScEvent(1.004, "out", "dev@example.com\r\n"),  # PTY echo with Enter
        ScEvent(1.005, "out", "Password: "),
        ScEvent(1.006, "cmd", "echo done"),
    ]
    result = d.post(events)
    out_texts = [e.text for e in result if e.type == "out"]
    # Characters stripped; \r\n retained so the cast shows a newline after typing
    assert "dev@example.com\r\n" not in out_texts  # full echo gone
    assert "\r\n" in out_texts                     # but the Enter echo preserved
    assert "Password: " in out_texts
    # \r\n must appear before "Password: " in the output
    rn_idx = next(i for i, t in enumerate(out_texts) if t == "\r\n")
    pw_idx = next(i for i, t in enumerate(out_texts) if t == "Password: ")
    assert rn_idx < pw_idx


def test_expect_directive_post_handles_raw_expect_call():
    """Bare 'cmd: expect' event (no SC expect directive) is handled correctly."""
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "cmd", "expect"),
        ScEvent(1.001, "out", "spawn ./fake-db"),
        ScEvent(1.002, "out", "Password:"),
        ScEvent(1.003, "cmd", "echo after"),
    ]
    result = d.post(events)
    assert result[0].type == "cmd"
    assert result[0].text == "./fake-db"
    assert any(e.type == "out" and "Password:" in e.text for e in result)
    assert ScEvent(1.003, "cmd", "echo after") in result


def test_expect_directive_post_terminates_on_dir_event():
    d = ExpectDirective()
    events = [
        ScEvent(1.0, "dir", "mark expect app"),
        ScEvent(1.001, "cmd", "expect"),
        ScEvent(1.002, "out", "spawn app"),
        ScEvent(1.003, "out", "some output"),
        ScEvent(1.004, "dir", "filter sed 's/x/y/g'"),
    ]
    result = d.post(events)
    assert ScEvent(1.004, "dir", "filter sed 's/x/y/g'") in result
    assert any(e.type == "out" and "some output" in e.text for e in result)


def test_filter_directive_post_passthrough_when_no_filter_set():
    d = FilterDirective()
    events = [ScEvent(1.0, "cmd", "echo hi"), ScEvent(1.1, "out", "hi")]
    assert d.post(events) == events


def test_filter_directive_post_registers_filter():
    d = FilterDirective()
    events = [ScEvent(1.0, "dir", "filter sed 's/foo/bar/g'")]
    result = d.post(events)
    assert result == []
    assert d.apply("foo baz") == "bar baz"


def test_filter_directive_post_registers_filter_add():
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter sed 's/foo/bar/g'")])
    d.post([ScEvent(1.1, "dir", "filter-add sed 's/baz/qux/g'")])
    assert d.apply("foo baz") == "bar qux"


def test_filter_directive_post_replaces_filter():
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter sed 's/a/b/g'")])
    d.post([ScEvent(1.1, "dir", "filter sed 's/x/y/g'")])
    assert d.apply("aaa xxx") == "aaa yyy"


def test_filter_directive_post_transforms_out_events():
    d = FilterDirective()
    events = [
        ScEvent(1.0, "dir", "filter sed 's/foo/bar/g'"),
        ScEvent(1.1, "out", "foo baz"),
    ]
    result = d.post(events)
    assert ScEvent(1.1, "out", "bar baz") in result
    assert not any(e.text == "foo baz" for e in result)


def test_filter_directive_post_transforms_cmd_events():
    d = FilterDirective()
    events = [
        ScEvent(1.0, "dir", "filter sed 's/foo/bar/g'"),
        ScEvent(1.1, "cmd", "foo command"),
    ]
    result = d.post(events)
    assert ScEvent(1.1, "cmd", "bar command") in result


def test_filter_directive_post_does_not_transform_dir_events():
    d = FilterDirective()
    events = [
        ScEvent(1.0, "dir", "filter sed 's/foo/bar/g'"),
        ScEvent(1.1, "dir", "scene intro"),
    ]
    result = d.post(events)
    assert ScEvent(1.1, "dir", "scene intro") in result


def test_filter_directive_apply_identity_when_empty():
    d = FilterDirective()
    assert d.apply("unchanged") == "unchanged"


def test_filter_directive_apply_real_command():
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter tr 'a-z' 'A-Z'")])
    assert d.apply("hello") == "HELLO"


def test_filter_directive_apply_preserves_cr_in_content():
    # text=True in subprocess would convert \r → \n via universal newlines;
    # binary mode must be used so progress-bar \r overwrite chars survive the filter.
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter sed 's/x/x/g'")])  # identity filter
    assert d.apply("frame1\rframe2\rframe3\r\n") == "frame1\rframe2\rframe3\r\n"


def test_filter_directive_failed_command_returns_empty():
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter false")])
    assert d.apply("anything") == ""


def test_filter_directive_command_not_found_returns_empty():
    d = FilterDirective()
    d.post([ScEvent(1.0, "dir", "filter __nonexistent_command_xyz__")])
    assert d.apply("anything") == ""


def test_record_directive_post_passthrough():
    d = RecordDirective()
    events = [ScEvent(1.0, "cmd", "echo hi"), ScEvent(1.1, "out", "hi")]
    assert d.post(events) == events


def test_record_directive_drops_pause_resume_block():
    d = RecordDirective()
    events = [
        ScEvent(1.0, "dir", "record pause"),
        ScEvent(1.1, "cmd", "PS1=>"),
        ScEvent(1.2, "cmd", "echo ignored"),
        ScEvent(1.3, "dir", "record resume"),
        ScEvent(1.4, "cmd", "echo after"),
    ]
    result = d.post(events)
    assert result == [ScEvent(1.4, "cmd", "echo after")]


def test_record_directive_drops_to_end_if_no_resume():
    d = RecordDirective()
    events = [
        ScEvent(1.0, "dir", "record pause"),
        ScEvent(1.1, "cmd", "echo something"),
    ]
    result = d.post(events)
    assert result == []


def test_record_directive_ignores_resume_without_pause():
    d = RecordDirective()
    events = [ScEvent(1.0, "dir", "record resume"), ScEvent(1.1, "cmd", "echo hi")]
    result = d.post(events)
    assert result == [ScEvent(1.0, "dir", "record resume"), ScEvent(1.1, "cmd", "echo hi")]


def test_set_directive_gen_mutates_active_config():
    d = SetDirective()
    active = ScriptcastConfig()
    active.type_speed = 40
    cursor, events = d.gen((1.0, "dir", "set type_speed 10"), deque(), active, 0.0)
    assert active.type_speed == 10
    assert cursor == 0.0
    assert events == []


def test_set_directive_gen_quoted_value():
    # bash traces `"$ "` as `'$ '`; shlex.split must handle shell quoting
    d = SetDirective()
    active = ScriptcastConfig()
    cursor, events = d.gen((1.0, "dir", "set prompt '$ '"), deque(), active, 0.0)
    assert active.prompt == "$ "
    assert cursor == 0.0
    assert events == []


def test_sleep_directive_gen_advances_cursor():
    d = SleepDirective()
    active = ScriptcastConfig()
    cursor, events = d.gen((1.0, "dir", "sleep 500"), deque(), active, 0.0)
    assert abs(cursor - 0.5) < 1e-9
    assert events == []


def test_sleep_directive_gen_zero():
    d = SleepDirective()
    active = ScriptcastConfig()
    cursor, events = d.gen((1.0, "dir", "sleep 0"), deque(), active, 1.5)
    assert cursor == 1.5


def test_comment_directive_post_passthrough():
    d = CommentDirective()
    events = [ScEvent(1.0, "cmd", "echo hi"), ScEvent(1.1, "out", "hi")]
    assert d.post(events) == events


def test_comment_directive_converts_comment_with_text():
    d = CommentDirective()
    events = [ScEvent(1.0, "dir", "'\\\' This is a comment")]
    result = d.post(events)
    assert result == [ScEvent(1.0, "cmd", "# This is a comment")]


def test_comment_directive_converts_empty_comment():
    d = CommentDirective()
    events = [ScEvent(1.0, "dir", "'\\\'")]
    result = d.post(events)
    assert result == [ScEvent(1.0, "cmd", "#")]


def test_comment_directive_does_not_touch_other_dir_events():
    d = CommentDirective()
    events = [ScEvent(1.0, "dir", "scene intro")]
    assert d.post(events) == events


def test_directive_has_priority():
    d = Directive()
    assert isinstance(d.priority, int)


def test_directive_has_handles_none_by_default():
    d = Directive()
    assert d.handles is None


def test_set_directive_handles_set():
    d = SetDirective()
    assert d.handles == "set"


def test_sleep_directive_handles_sleep():
    d = SleepDirective()
    assert d.handles == "sleep"


def test_expect_directive_priority_lower_than_filter():
    assert ExpectDirective().priority < FilterDirective().priority


def test_expect_directive_handles_expect_input():
    d = ExpectDirective()
    assert d.handles == "expect-input"


def test_expect_directive_gen_advances_cursor_by_input_wait():
    from collections import deque
    from scriptcast.config import ScriptcastConfig
    d = ExpectDirective()
    active = ScriptcastConfig()
    active.input_wait = 300
    active.type_speed = 0
    cursor, lines = d.gen((1.0, "dir", "expect-input secret"), deque(), active, 0.0)
    assert cursor == pytest.approx(0.3)


def test_expect_directive_gen_emits_chars():
    from collections import deque
    from scriptcast.config import ScriptcastConfig
    d = ExpectDirective()
    active = ScriptcastConfig()
    active.input_wait = 0
    active.type_speed = 0
    _, lines = d.gen((1.0, "dir", "expect-input hi"), deque(), active, 0.0)
    cast_texts = [json.loads(ln)[2] for ln in lines]
    assert "h" in cast_texts
    assert "i" in cast_texts
    assert "\r\n" not in cast_texts
    event_types = {json.loads(ln)[1] for ln in lines}
    assert event_types == {"o"}


def test_expect_directive_gen_empty_input():
    from collections import deque
    from scriptcast.config import ScriptcastConfig
    d = ExpectDirective()
    active = ScriptcastConfig()
    active.input_wait = 0
    active.type_speed = 0
    cursor, lines = d.gen((1.0, "dir", "expect-input"), deque(), active, 0.0)
    assert lines == []


def test_helpers_directive_priority_is_lowest():
    from scriptcast.directives import build_directives
    all_directives = build_directives()
    helpers = next(d for d in all_directives if isinstance(d, HelpersDirective))
    others = [d for d in all_directives if not isinstance(d, HelpersDirective)]
    assert all(helpers.priority < d.priority for d in others)


def test_helpers_directive_pre_passthrough():
    d = HelpersDirective()
    lines = ["echo hello\n", "exit 0\n"]
    assert d.pre(lines) == lines


def test_helpers_directive_pre_expands_helpers_line():
    d = HelpersDirective()
    lines = [": SC helpers\n", "echo hi\n"]
    result = d.pre(lines)
    joined = "".join(result)
    assert ": SC record pause\n" in joined
    assert "RED=$'\\033[31m'\n" in joined
    assert "YELLOW=$'\\033[33m'\n" in joined
    assert "GREEN=$'\\033[32m'\n" in joined
    assert "CYAN=$'\\033[36m'\n" in joined
    assert "BOLD=$'\\033[1m'\n" in joined
    assert "RESET=$'\\033[0m'\n" in joined
    assert ": SC record resume\n" in joined
    assert "echo hi\n" in joined
    assert ": SC helpers\n" not in joined


def test_helpers_directive_pre_custom_prefix():
    d = HelpersDirective(dp="MY")
    lines = [": MY helpers\n"]
    result = d.pre(lines)
    joined = "".join(result)
    assert ": MY record pause\n" in joined
    assert ": MY record resume\n" in joined


def test_helpers_directive_pre_ignores_partial_match():
    d = HelpersDirective()
    lines = [": SC helpers extra\n"]
    assert d.pre(lines) == lines


def test_helpers_directive_post_passthrough():
    d = HelpersDirective()
    events = [ScEvent(1.0, "cmd", "echo hi")]
    assert d.post(events) == events
