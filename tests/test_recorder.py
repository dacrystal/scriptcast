# tests/test_recorder.py
import json
import logging
import shutil
from unittest.mock import MagicMock

import pytest

from scriptcast.config import ScriptcastConfig
from scriptcast.directives import ScEvent
from scriptcast.recorder import _parse_raw, _postprocess, _preprocess, _serialise, record


def test_record_creates_sc_file(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    assert sc_path.exists()


def test_sc_file_has_jsonl_header(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    first_line = sc_path.read_text().splitlines()[0]
    header = json.loads(first_line)
    assert header["version"] == 1
    assert "shell" in header
    assert header["directive-prefix"] == "SC"
    assert "width" in header
    assert "height" in header
    assert header["pipeline-version"] == 3


def test_sc_file_contains_output_event(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo scriptcast_test_marker\n")
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    events = [json.loads(ln) for ln in sc_path.read_text().splitlines()[1:] if ln.strip()]
    assert any(e[1] == "out" and "scriptcast_test_marker" in e[2] for e in events)


def test_record_nonzero_exit_writes_sc_and_warns(tmp_path, caplog):
    script = tmp_path / "demo.sh"
    script.write_text("echo before\nexit 1\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    with caplog.at_level(logging.WARNING):
        record(script, sc_path, config, shell)
    assert sc_path.exists()
    assert "non-zero" in caplog.text


def test_record_strips_shebang(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("#!/usr/bin/env scriptcast\necho hello\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    content = sc_path.read_text()
    assert "hello" in content


def test_preprocess_mock_rewrites_directive():
    script = (
        ": SC mock deploy arg1 <<'EOF'\n"
        "Deploying...\n"
        "OK\n"
        "EOF\n"
    )
    result = _preprocess(script)
    assert "(: SC mark mock; set +x; echo + deploy arg1; cat) <<'EOF'" in result
    assert "Deploying..." in result
    assert result.endswith("EOF\n")  # closing delimiter preserved
    assert ": SC mock" not in result
    # Verify only one closing "EOF\n" (not multiple)
    lines = result.split('\n')
    eof_lines = [ln for ln in lines if ln == 'EOF']
    assert len(eof_lines) == 1


def test_preprocess_mock_passes_through_non_mock_lines():
    script = "echo hello\n: SC scene intro\n"
    result = _preprocess(script)
    assert result == script


def test_preprocess_mock_uses_directive_prefix():
    script = ": MY mock cmd <<'EOF'\nout\nEOF\n"
    result = _preprocess(script, directive_prefix="MY")
    assert "(: MY mark mock; set +x; echo + cmd; cat) <<'EOF'" in result


def test_preprocess_mock_multiline_body():
    script = (
        ": SC mock git status <<'DONE'\n"
        "On branch main\n"
        "nothing to commit\n"
        "DONE\n"
    )
    result = _preprocess(script)
    assert "echo + git status" in result
    assert "On branch main" in result
    assert "nothing to commit" in result
    assert result.endswith("DONE\n")


def test_preprocess_expect_rewrites_directive():
    script = (
        ": SC expect mysql -u root <<'EOF'\n"
        'expect "Password:"\n'
        'send "secret\\r"\n'
        "EOF\n"
    )
    result = _preprocess(script)
    assert "expect <<'EOF'" in result
    assert "spawn mysql -u root" in result
    assert 'send_user ": SC mark input secret\\n"' in result
    assert 'send "secret\\r"' in result
    assert ": SC expect" not in result


def test_preprocess_expect_injects_marker_before_each_send():
    script = (
        ": SC expect cmd <<'EOF'\n"
        'expect "p1"\n'
        'send "a\\r"\n'
        'expect "p2"\n'
        'send "b\\r"\n'
        "EOF\n"
    )
    result = _preprocess(script)
    assert result.count('send_user ": SC mark input') == 2
    assert 'send_user ": SC mark input a\\n"' in result
    assert 'send_user ": SC mark input b\\n"' in result


def test_preprocess_expect_prepends_spawn():
    script = ": SC expect myapp arg1 arg2 <<'EOF'\nexpect \"done\"\nEOF\n"
    result = _preprocess(script)
    lines = result.splitlines()
    # First line after expect <<'EOF' should be spawn
    eof_idx = next(i for i, ln in enumerate(lines) if ln.startswith("expect <<"))
    assert lines[eof_idx + 1] == "spawn myapp arg1 arg2"


def _parse_sc_events(sc_text):
    return [json.loads(ln) for ln in sc_text.splitlines() if ln.strip()]


def test_postprocess_emits_cmd_event():
    raw = "1.000 + echo hello\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "cmd" and e[2] == "echo hello" for e in events)


def test_postprocess_emits_output_event():
    raw = "1.000 hello\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "out" and "hello" in e[2] for e in events)


def test_postprocess_emits_generator_directive():
    raw = "1.000 + : SC scene intro\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "dir" and e[2] == "scene intro" for e in events)


def test_postprocess_strips_mock_marker_and_set_x():
    raw = (
        "1.000 + : SC mark mock\n"
        "1.001 + set +x\n"
        "1.002 + deploy arg1\n"
        "1.003 Deploying...\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    texts = [e[2] for e in events]
    assert not any("mark mock" in t for t in texts)
    assert not any("set +x" in t for t in texts)
    assert any(e[1] == "cmd" and "deploy arg1" in e[2] for e in events)
    assert any(e[1] == "out" and "Deploying..." in e[2] for e in events)


def test_postprocess_strips_expect_trace():
    raw = "1.000 + expect\n1.001 spawn ./fake-db\n1.002 Password:\n"
    events = _parse_sc_events(_postprocess(raw))
    assert not any(e[1] == "cmd" and e[2] == "expect" for e in events)
    assert not any("spawn" in e[2] for e in events)
    assert any(e[1] == "out" and "Password:" in e[2] for e in events)


def test_postprocess_strips_expect_trace_with_args():
    raw = "1.000 + expect somefile.exp\n1.001 output\n"
    events = _parse_sc_events(_postprocess(raw))
    assert not any(e[1] == "cmd" and "expect" in e[2] for e in events)


def test_postprocess_drops_record_pause_content():
    raw = (
        "1.000 + : SC record pause\n"
        "1.001 + PS1=>\n"
        "1.002 + : SC record resume\n"
        "1.003 + echo after\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    texts = [e[2] for e in events]
    assert not any("PS1" in t for t in texts)
    assert any("echo after" in t for t in texts)


def test_postprocess_filter_applies_to_output():
    raw = (
        "1.000 + : SC filter sed 's/foo/bar/g'\n"
        "1.001 foo baz\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    output_texts = [e[2] for e in events if e[1] == "out"]
    assert any("bar baz" in t for t in output_texts)
    assert not any("foo" in t for t in output_texts)


def test_postprocess_filter_not_emitted_as_directive():
    raw = "1.000 + : SC filter sed 's/a/b/g'\n"
    events = _parse_sc_events(_postprocess(raw))
    assert not any(e[1] == "dir" and "filter" in e[2] for e in events)


def test_postprocess_filter_add_appends():
    raw = (
        "1.000 + : SC filter sed 's/foo/bar/g'\n"
        "1.001 + : SC filter-add sed 's/baz/qux/g'\n"
        "1.002 foo baz\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    output_texts = [e[2] for e in events if e[1] == "out"]
    assert any("bar qux" in t for t in output_texts)


def test_postprocess_custom_trace_prefix():
    raw = "1.000 ++ echo hi\n"
    events = _parse_sc_events(_postprocess(raw, trace_prefix="++"))
    assert any(e[1] == "cmd" and e[2] == "echo hi" for e in events)


def test_postprocess_emits_expect_input_dir_event():
    raw = (
        "1.000 + expect myapp\n"
        "1.001 spawn myapp\n"
        "1.002 : SC mark input secret\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "dir" and "expect-input" in e[2] for e in events)


def test_postprocess_emits_output_prefix_before_expect_input():
    raw = (
        "1.000 + expect myapp\n"
        "1.001 spawn myapp\n"
        "1.002 Password: : SC mark input secret\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    types = [e[1] for e in events]
    assert "out" in types
    assert any(e[1] == "dir" and "expect-input" in e[2] for e in events)
    assert types.index("out") < types.index("dir")


def test_postprocess_strips_pty_echo_after_input():
    raw = (
        "1.000 + expect\n"
        "1.001 spawn ./fake-db\n"
        "1.002 Password: : SC mark input secret\n"
        "1.003 secret\n"
        "1.004 Welcome to FakeDB\n"
        "1.005 mysql> : SC mark input show databases;\n"
        "1.006 show databases;\n"
        "1.007 (0 rows)\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    output_texts = [e[2] for e in events if e[1] == "out"]
    assert not any("secret" in t for t in output_texts)
    assert not any("show databases;" in t for t in output_texts)
    assert any("Welcome to FakeDB" in t for t in output_texts)
    assert any("(0 rows)" in t for t in output_texts)


def test_record_mock_directive_produces_cmd_and_output_events(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text(": SC mock deploy <<'EOF'\nDeploying...\nEOF\n")
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    events = [json.loads(ln) for ln in sc_path.read_text().splitlines()[1:] if ln.strip()]
    assert any(e[1] == "cmd" and "deploy" in e[2] for e in events)
    assert any(e[1] == "out" and "Deploying..." in e[2] for e in events)
    assert not any("mark mock" in e[2] for e in events)
    assert not any("set +x" in e[2] for e in events)


def test_preprocess_expect_injects_send_text_in_marker():
    script = (
        ": SC expect cmd <<'EOF'\n"
        'expect "Password:"\n'
        'send "secret\\r"\n'
        "EOF\n"
    )
    result = _preprocess(script)
    assert 'send_user ": SC mark input secret\\n"' in result


def test_record_cwd_is_script_directory(tmp_path):
    """record() runs the script with cwd set to the script's parent directory."""
    script = tmp_path / "demo.sh"
    helper = tmp_path / "helper.txt"
    helper.write_text("hello from helper\n")
    script.write_text("cat helper.txt\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    content = sc_path.read_text()
    assert "hello from helper" in content



def test_parse_raw_cmd_line():
    events = _parse_raw("1.000 + echo hello\n", "+", "SC")
    assert events == [ScEvent(1.0, "cmd", "echo hello")]


def test_parse_raw_cmd_strips_trailing_cr():
    # PTY CRLF: \r before \n is a PTY artifact and must be stripped from cmd text.
    events = _parse_raw("1.000 + echo hello\r\n", "+", "SC")
    assert events == [ScEvent(1.0, "cmd", "echo hello")]


def test_parse_raw_output_line():
    events = _parse_raw("1.000 hello world\n", "+", "SC")
    assert events == [ScEvent(1.0, "out", "hello world\n")]


def test_parse_raw_directive_line():
    events = _parse_raw("1.000 + : SC scene intro\n", "+", "SC")
    assert events == [ScEvent(1.0, "dir", "scene intro")]


def test_parse_raw_dir_strips_trailing_cr():
    # PTY CRLF: \r before \n is a PTY artifact and must be stripped from dir text.
    events = _parse_raw("1.000 + : SC scene intro\r\n", "+", "SC")
    assert events == [ScEvent(1.0, "dir", "scene intro")]


def test_parse_raw_skips_non_float_lines():
    events = _parse_raw("not_a_number + echo hi\n", "+", "SC")
    assert events == []



def test_parse_raw_custom_prefix():
    events = _parse_raw("1.000 ++ echo hi\n", "++", "SC")
    assert events == [ScEvent(1.0, "cmd", "echo hi")]


def test_serialise_cmd():
    events = [ScEvent(1.0, "cmd", "echo hi")]
    lines = _serialise(events).splitlines()
    assert json.loads(lines[0]) == [1.0, "cmd", "echo hi"]


def test_serialise_out():
    events = [ScEvent(1.0, "out", "hello")]
    lines = _serialise(events).splitlines()
    assert json.loads(lines[0]) == [1.0, "out", "hello"]


def test_serialise_dir():
    events = [ScEvent(1.0, "dir", "scene intro")]
    lines = _serialise(events).splitlines()
    assert json.loads(lines[0]) == [1.0, "dir", "scene intro"]


def test_serialise_empty():
    assert _serialise([]) == ""


def test_parse_raw_out_preserves_cr_in_content():
    # With the simplified split-on-\n approach, bare \r is content, not a
    # record separator. A line containing bare \r yields a single out event
    # with the \r embedded in the text.
    events = _parse_raw("1.000 Loading\r100%\n", "+", "SC")
    assert events == [ScEvent(1.0, "out", "Loading\r100%\n")]


def test_parse_raw_out_preserves_crlf():
    # CRLF line ending: \r is kept, \n is the record separator
    events = _parse_raw("1.000 hello\r\n", "+", "SC")
    assert events == [ScEvent(1.0, "out", "hello\r\n")]


def test_parse_raw_out_no_terminator_for_last_entry():
    # A prompt with no trailing newline — last entry in the log
    events = _parse_raw("1.000 Enter password: ", "+", "SC")
    assert events == [ScEvent(1.0, "out", "Enter password: ")]


def test_record_isatty_in_pty(tmp_path):
    """Script sees a real TTY — isatty(stdout) is true."""
    script = tmp_path / "demo.sh"
    script.write_text('[ -t 1 ] && echo is_tty || echo not_tty\n')
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    content = sc_path.read_text()
    assert "is_tty" in content
    assert "not_tty" not in content


def test_record_pty_translates_lf_to_crlf(tmp_path):
    """PTY line discipline translates bare \\n to \\r\\n in out events."""
    script = tmp_path / "demo.sh"
    script.write_text('printf "hello\\n"\n')
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    events = [json.loads(ln) for ln in sc_path.read_text().splitlines()[1:] if ln.strip()]
    out_texts = [e[2] for e in events if e[1] == "out"]
    assert any("hello\r\n" in t for t in out_texts)


def test_record_xtrace_log_creates_file(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell, xtrace_log=True)
    xtrace_path = tmp_path / "demo.xtrace"
    assert xtrace_path.exists()


def test_record_xtrace_log_contains_raw_output(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo scriptcast_xtrace_marker\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell, xtrace_log=True)
    xtrace_path = tmp_path / "demo.xtrace"
    assert "scriptcast_xtrace_marker" in xtrace_path.read_text()


def test_record_no_xtrace_log_by_default(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    xtrace_path = tmp_path / "demo.xtrace"
    assert not xtrace_path.exists()


def test_postprocess_applies_unescape_to_dir_events():
    """adapter.unescape_xtrace is called on dir events, not cmd or out events."""
    adapter = MagicMock()
    adapter.unescape_xtrace.side_effect = lambda t: t.replace("BEFORE", "AFTER")

    raw = (
        "1.0 + : SC scene main\n"
        "1.1 + echo hi\n"
        "1.2 hello\n"
    )
    _postprocess(raw, adapter=adapter)

    # called once for the dir event "scene main", not for cmd or out
    assert adapter.unescape_xtrace.call_count == 1
    adapter.unescape_xtrace.assert_called_with("scene main")


def test_postprocess_unescape_transforms_dir_text():
    """unescape result is used as the directive text in the .sc output."""
    adapter = MagicMock()
    adapter.unescape_xtrace.return_value = "set prompt \x1b[92m> \x1b[0m"

    raw = "1.0 + : SC set prompt $'\\C-[[92m> \\C-[[0m'\n"
    sc_body = _postprocess(raw, adapter=adapter)

    events = [json.loads(line) for line in sc_body.strip().splitlines()]
    assert events[0][1] == "dir"
    assert events[0][2] == "set prompt \x1b[92m> \x1b[0m"


def test_record_zsh_prompt_esc_bytes(tmp_path):
    """zsh $'...' prompt survives record → .sc with correct ESC bytes."""
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh not available")

    script = tmp_path / "t.sh"
    # $'\x1b[92m> \x1b[0m' expands to ESC bytes; zsh xtrace uses $'\C-[...'
    script.write_text(": SC set prompt $'\\x1b[92m> \\x1b[0m'\n")
    sc_path = tmp_path / "t.sc"
    record(script, sc_path, ScriptcastConfig(), zsh)

    lines = sc_path.read_text().splitlines()
    dir_events = [
        json.loads(ln) for ln in lines[1:]
        if json.loads(ln)[1] == "dir" and json.loads(ln)[2].startswith("set prompt")
    ]
    assert dir_events, "no 'set prompt' dir event found in .sc"
    assert dir_events[0][2] == "set prompt \x1b[92m> \x1b[0m"
