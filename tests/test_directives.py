from collections import deque
from scriptcast.directives import Directive, RecorderDirective, GeneratorDirective, MockDirective, ExpectDirective, FilterDirective, RecordDirective, ScDirective, SetDirective, SleepDirective
from scriptcast.config import ScriptcastConfig
import json


def test_directive_pre_returns_none():
    d = Directive()
    assert d.pre(deque(["hello\n"])) is None


def test_directive_post_returns_none():
    d = Directive()
    assert d.post(deque([(1.0, "hello")])) is None


def test_directive_gen_noop():
    d = Directive()
    q = deque()
    cfg = ScriptcastConfig()
    cursor, events = d.gen((1.0, "output", "hi"), q, cfg, 0.0)
    assert cursor == 0.0
    assert events == []


def test_mock_directive_pre_returns_none_for_non_mock():
    d = MockDirective()
    assert d.pre(deque(["echo hello\n"])) is None


def test_mock_directive_pre_rewrites():
    d = MockDirective()
    q = deque([
        ": SC mock deploy <<'EOF'\n",
        "Deploying...\n",
        "OK\n",
        "EOF\n",
    ])
    result = d.pre(q)
    assert result is not None
    assert "(: SC mark mock; set +x; echo + deploy; cat) <<'EOF'\n" in result
    assert "Deploying...\n" in result
    assert "OK\n" in result
    assert "EOF\n" in result
    assert len(q) == 0  # queue consumed


def test_mock_directive_pre_custom_prefix():
    d = MockDirective(dp="MY")
    q = deque([": MY mock cmd <<'DONE'\n", "output\n", "DONE\n"])
    result = d.pre(q)
    assert result is not None
    assert "(: MY mark mock; set +x; echo + cmd; cat) <<'DONE'\n" in result


def test_mock_directive_post_returns_none_for_non_mock():
    d = MockDirective()
    assert d.post(deque([(1.0, "something else")])) is None


def test_mock_directive_post_pops_set_x():
    d = MockDirective()
    q = deque([
        (1.0, "+ : SC mark mock"),
        (1.001, "+ set +x"),
    ])
    events = d.post(q)
    assert events == []
    assert len(q) == 0  # mark mock + set +x both consumed


def test_expect_directive_pre_returns_none_for_non_match():
    d = ExpectDirective()
    assert d.pre(deque([": SC mock cmd <<'EOF'\n"])) is None


def test_expect_directive_pre_rewrites():
    d = ExpectDirective()
    q = deque([
        ": SC expect mysql <<'EOF'\n",
        'expect "Password:"\n',
        'send "secret\\r"\n',
        "EOF\n",
    ])
    result = d.pre(q)
    assert result is not None
    joined = "".join(result)
    assert ": SC mark expect mysql" in joined
    assert "expect <<'EOF'" in joined
    assert "spawn mysql" in joined
    assert 'send_user ": SC mark input secret\\n"' in joined
    assert 'send "secret\\r"' in joined
    assert len(q) == 0


def test_expect_directive_pre_no_send():
    d = ExpectDirective()
    q = deque([": SC expect app <<'EOF'\n", 'expect "done"\n', "EOF\n"])
    result = d.pre(q)
    assert result is not None
    joined = "".join(result)
    assert "spawn app" in joined
    assert "mark input" not in joined


def test_expect_directive_post_returns_none_for_non_match():
    d = ExpectDirective()
    assert d.post(deque([(1.0, "something else")])) is None


def test_expect_directive_post_emits_cmd():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect mysql"),
        (1.001, "+ expect"),
        (1.002, "spawn mysql"),
        (1.003, "Password:"),
        (1.004, "+ echo hi"),
    ])
    events = d.post(q)
    types = [json.loads(e)[1] for e in events]
    assert "cmd" in types
    assert json.loads(events[0]) == [1.0, "cmd", "mysql"]


def test_expect_directive_post_skips_spawn_line():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect myapp"),
        (1.001, "+ expect"),
        (1.002, "spawn myapp"),
        (1.003, "+ echo done"),
    ])
    events = d.post(q)
    texts = [json.loads(e)[2] for e in events]
    assert not any("spawn" in t for t in texts)


def test_expect_directive_post_handles_mark_input_silent():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, "Password: : SC mark input secret"),
        (1.004, "Welcome"),
        (1.005, "+ echo done"),
    ])
    events = d.post(q)
    types_texts = [(json.loads(e)[1], json.loads(e)[2]) for e in events]
    assert ("output", "Password: ") in types_texts
    assert ("input", "") in types_texts
    assert ("output", "Welcome") in types_texts


def test_expect_directive_post_strips_pty_echo():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, "prompt> : SC mark input show;"),
        (1.004, "show;"),   # pty echo — must be stripped
        (1.005, "(0 rows)"),
        (1.006, "+ echo done"),
    ])
    events = d.post(q)
    output_texts = [json.loads(e)[2] for e in events if json.loads(e)[1] == "output"]
    assert "show;" not in output_texts
    assert "(0 rows)" in output_texts


def test_expect_directive_post_pushes_back_terminator():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, "+ echo after"),
    ])
    d.post(q)
    assert len(q) == 1
    assert q[0][1] == "+ echo after"


def test_expect_directive_post_terminates_on_sc_directive():
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, "some output"),
        (1.004, "+ : SC filter sed 's/x/y/g'"),
    ])
    events = d.post(q)
    assert len(q) == 1
    assert q[0][1] == "+ : SC filter sed 's/x/y/g'"
    output_texts = [json.loads(e)[2] for e in events if json.loads(e)[1] == "output"]
    assert "some output" in output_texts


def test_expect_directive_post_applies_filter():
    d = ExpectDirective(filter_apply=lambda t: t.replace("hello", "bye"))
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, "hello world"),
        (1.004, "+ echo done"),
    ])
    events = d.post(q)
    output_texts = [json.loads(e)[2] for e in events if json.loads(e)[1] == "output"]
    assert "bye world" in output_texts


def test_expect_directive_post_handles_empty_prefix_mark_input():
    """Mark input line with no output before the colon must not terminate the session."""
    d = ExpectDirective()
    q = deque([
        (1.0, "+ : SC mark expect app"),
        (1.001, "+ expect"),
        (1.002, "spawn app"),
        (1.003, ": SC mark input secret"),   # empty prefix — was escaping session before fix
        (1.004, "+ echo done"),
    ])
    events = d.post(q)
    types = [json.loads(e)[1] for e in events]
    assert "input" in types
    # Session terminates correctly; terminator stays in queue
    assert len(q) == 1
    assert q[0][1] == "+ echo done"


def test_filter_directive_post_returns_none_for_non_filter():
    d = FilterDirective()
    assert d.post(deque([(1.0, "something else")])) is None


def test_filter_directive_post_replaces_text():
    d = FilterDirective()
    d.post(deque([(1.0, "+ : SC filter sed 's/foo/bar/g'")]))
    assert d.apply("foo baz") == "bar baz"


def test_filter_directive_post_replaces_existing_filter():
    d = FilterDirective()
    d.post(deque([(1.0, "+ : SC filter sed 's/a/b/g'")]))
    d.post(deque([(1.1, "+ : SC filter sed 's/x/y/g'")]))
    assert d.apply("aaa xxx") == "aaa yyy"


def test_filter_directive_post_filter_add_appends():
    d = FilterDirective()
    d.post(deque([(1.0, "+ : SC filter sed 's/foo/bar/g'")]))
    d.post(deque([(1.1, "+ : SC filter-add sed 's/baz/qux/g'")]))
    assert d.apply("foo baz") == "bar qux"


def test_filter_directive_apply_identity_when_empty():
    d = FilterDirective()
    assert d.apply("unchanged") == "unchanged"


def test_filter_directive_transforms_output_in_place():
    d = FilterDirective()
    # Set up filter
    d.post(deque([(1.0, "+ : SC filter sed 's/foo/bar/g'")]))
    # Transform output line in-place
    q = deque([(1.1, "foo baz")])
    result = d.post(q)
    assert result is None          # not consumed — else branch emits it
    assert q[0] == (1.1, "bar baz")  # content mutated


def test_filter_directive_does_not_transform_trace_lines():
    d = FilterDirective()
    d.post(deque([(1.0, "+ : SC filter sed 's/foo/bar/g'")]))
    q = deque([(1.1, "+ foo command")])
    result = d.post(q)
    assert result is None
    assert q[0] == (1.1, "+ foo command")  # unchanged


def test_record_directive_post_returns_none_for_non_record():
    d = RecordDirective()
    assert d.post(deque([(1.0, "something else")])) is None


def test_record_directive_consumes_pause_block():
    d = RecordDirective()
    q = deque([
        (1.0, "+ : SC record pause"),
        (1.1, "+ PS1=>"),
        (1.2, "+ echo ignored"),
        (1.3, "+ : SC record resume"),
        (1.4, "+ echo after"),
    ])
    result = d.post(q)
    assert result == []
    assert len(q) == 1
    assert q[0] == (1.4, "+ echo after")


def test_record_directive_returns_none_for_resume_alone():
    d = RecordDirective()
    q = deque([(1.0, "+ : SC record resume")])
    result = d.post(q)
    assert result is None


def test_record_directive_consumes_until_end_if_no_resume():
    d = RecordDirective()
    q = deque([
        (1.0, "+ : SC record pause"),
        (1.1, "+ echo something"),
    ])
    result = d.post(q)
    assert result == []
    assert len(q) == 0


def test_set_directive_gen_mutates_active_config():
    d = SetDirective()
    active = ScriptcastConfig()
    active.type_speed = 40
    cursor, events = d.gen((1.0, "directive", "set type_speed 10"), deque(), active, 0.0)
    assert active.type_speed == 10
    assert cursor == 0.0
    assert events == []


def test_sleep_directive_gen_advances_cursor():
    d = SleepDirective()
    active = ScriptcastConfig()
    cursor, events = d.gen((1.0, "directive", "sleep 500"), deque(), active, 0.0)
    assert abs(cursor - 0.5) < 1e-9
    assert events == []


def test_sleep_directive_gen_zero():
    d = SleepDirective()
    active = ScriptcastConfig()
    cursor, events = d.gen((1.0, "directive", "sleep 0"), deque(), active, 1.5)
    assert cursor == 1.5


def test_sc_directive_emits_directive_event():
    sc_d = ScDirective()
    q = deque([(1.0, "+ : SC scene intro")])
    result = sc_d.post(q)
    assert result == [json.dumps([1.0, "directive", "scene intro"])]
    assert len(q) == 0


def test_sc_directive_emits_multi_word():
    sc_d = ScDirective()
    q = deque([(1.0, "+ : SC set type_speed 40")])
    result = sc_d.post(q)
    assert result == [json.dumps([1.0, "directive", "set type_speed 40"])]
    assert len(q) == 0


def test_sc_directive_returns_none_for_non_sc_line():
    sc_d = ScDirective()
    q = deque([(1.0, "hello output")])
    result = sc_d.post(q)
    assert result is None
    assert len(q) == 1


def test_sc_directive_returns_none_for_trace_line():
    sc_d = ScDirective()
    q = deque([(1.0, "+ echo hello")])
    result = sc_d.post(q)
    assert result is None


def test_sc_directive_custom_prefix():
    sc_d = ScDirective(dp="MY", tp=">>")
    q = deque([(1.0, ">> : MY scene intro")])
    result = sc_d.post(q)
    assert result == [json.dumps([1.0, "directive", "scene intro"])]
