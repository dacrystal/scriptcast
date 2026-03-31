# tests/test_recorder.py
import json
import shutil
import pytest
from pathlib import Path
from scriptcast.recorder import record, _preprocess, _postprocess
from scriptcast.config import ScriptcastConfig


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


def test_sc_file_contains_output_event(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo scriptcast_test_marker\n")
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    events = [json.loads(l) for l in sc_path.read_text().splitlines()[1:] if l.strip()]
    assert any(e[1] == "output" and "scriptcast_test_marker" in e[2] for e in events)


def test_record_nonzero_exit_writes_sc_and_warns(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo before\nexit 1\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    with pytest.warns(UserWarning, match="non-zero"):
        record(script, sc_path, config, shell)
    assert sc_path.exists()


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
    eof_lines = [l for l in lines if l == 'EOF']
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
    eof_idx = next(i for i, l in enumerate(lines) if l.startswith("expect <<"))
    assert lines[eof_idx + 1] == "spawn myapp arg1 arg2"


def _parse_sc_events(sc_text):
    return [json.loads(l) for l in sc_text.splitlines() if l.strip()]


def test_postprocess_emits_cmd_event():
    raw = "1.000 + echo hello\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "cmd" and e[2] == "echo hello" for e in events)


def test_postprocess_emits_output_event():
    raw = "1.000 hello\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "output" and e[2] == "hello" for e in events)


def test_postprocess_emits_generator_directive():
    raw = "1.000 + : SC scene intro\n"
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "directive" and e[2] == "scene intro" for e in events)


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
    assert any(e[1] == "output" and "Deploying..." in e[2] for e in events)


def test_postprocess_strips_expect_trace():
    raw = "1.000 + expect\n1.001 spawn ./fake-db\n1.002 Password:\n"
    events = _parse_sc_events(_postprocess(raw))
    assert not any(e[1] == "cmd" and e[2] == "expect" for e in events)
    assert not any("spawn" in e[2] for e in events)
    assert any(e[1] == "output" and "Password:" in e[2] for e in events)


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
    output_texts = [e[2] for e in events if e[1] == "output"]
    assert any("bar baz" in t for t in output_texts)
    assert not any("foo" in t for t in output_texts)


def test_postprocess_filter_not_emitted_as_directive():
    raw = "1.000 + : SC filter sed 's/a/b/g'\n"
    events = _parse_sc_events(_postprocess(raw))
    assert not any(e[1] == "directive" and "filter" in e[2] for e in events)


def test_postprocess_filter_add_appends():
    raw = (
        "1.000 + : SC filter sed 's/foo/bar/g'\n"
        "1.001 + : SC filter-add sed 's/baz/qux/g'\n"
        "1.002 foo baz\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    output_texts = [e[2] for e in events if e[1] == "output"]
    assert any("bar qux" in t for t in output_texts)


def test_postprocess_emits_input_event_for_mark_input():
    raw = (
        "1.000 + expect myapp\n"
        "1.001 spawn myapp\n"
        "1.002 : SC mark input secret\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "input" for e in events)


def test_postprocess_emits_output_prefix_before_input():
    raw = (
        "1.000 + expect myapp\n"
        "1.001 spawn myapp\n"
        "1.002 Password: : SC mark input secret\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    types = [e[1] for e in events]
    assert "output" in types and "input" in types
    assert types.index("output") < types.index("input")


def test_postprocess_mark_input_empty_prefix_stays_in_session():
    """Mark input line with empty output prefix must not escape the expect session."""
    raw = (
        "1.000 + : SC mark expect ./myapp\n"
        "1.001 spawn ./myapp\n"
        "1.002 : SC mark input secret\n"
        "1.003 + echo after\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    assert any(e[1] == "input" for e in events)
    assert any(e[1] == "cmd" and "echo after" in e[2] for e in events)


def test_postprocess_custom_trace_prefix():
    raw = "1.000 ++ echo hi\n"
    events = _parse_sc_events(_postprocess(raw, trace_prefix="++"))
    assert any(e[1] == "cmd" and e[2] == "echo hi" for e in events)


def test_postprocess_emits_cmd_for_spawn_after_expect_trace():
    raw = (
        "1.000 + expect\n"
        "1.001 spawn ./fake-db\n"
        "1.002 Password: : SC mark input secret\n"
    )
    events = _parse_sc_events(_postprocess(raw))
    texts = [e[2] for e in events]
    assert not any("spawn" in t for t in texts)
    assert any(e[1] == "cmd" and e[2] == "./fake-db" for e in events)
    # No pty echo follows, so input is silent (empty string)
    assert any(e[1] == "input" and e[2] == "" for e in events)


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
    output_texts = [e[2] for e in events if e[1] == "output"]
    assert "secret" not in output_texts
    assert "show databases;" not in output_texts
    assert "Welcome to FakeDB" in output_texts
    assert "(0 rows)" in output_texts


def test_record_mock_directive_produces_cmd_and_output_events(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text(": SC mock deploy <<'EOF'\nDeploying...\nEOF\n")
    sc_path = tmp_path / "demo.sc"
    record(script, sc_path, ScriptcastConfig(), shutil.which("bash"))
    events = [json.loads(l) for l in sc_path.read_text().splitlines()[1:] if l.strip()]
    assert any(e[1] == "cmd" and "deploy" in e[2] for e in events)
    assert any(e[1] == "output" and "Deploying..." in e[2] for e in events)
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
