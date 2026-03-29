# tests/test_recorder.py
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


def test_sc_file_has_header(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    content = sc_path.read_text()
    assert "#shell=bash" in content
    assert "#trace-prefix=+" in content
    assert "#directive-prefix=SC" in content


def test_sc_file_contains_output(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo scriptcast_test_marker\n")
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    content = sc_path.read_text()
    assert "scriptcast_test_marker" in content


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
    assert 'send_user ": SC mark input"' in result
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
    assert result.count('send_user ": SC mark input"') == 2


def test_preprocess_expect_prepends_spawn():
    script = ": SC expect myapp arg1 arg2 <<'EOF'\nexpect \"done\"\nEOF\n"
    result = _preprocess(script)
    lines = result.splitlines()
    # First line after expect <<'EOF' should be spawn
    eof_idx = next(i for i, l in enumerate(lines) if l.startswith("expect <<"))
    assert lines[eof_idx + 1] == "spawn myapp arg1 arg2"


def test_postprocess_strips_mock_marker_and_set_x():
    raw = (
        "1.000 + : SC mark mock\n"
        "1.001 + set +x\n"
        "1.002 + deploy arg1\n"
        "1.003 Deploying...\n"
    )
    result = _postprocess(raw)
    assert "+ : SC mark mock" not in result
    assert "+ set +x" not in result
    assert "+ deploy arg1" in result
    assert "Deploying..." in result

def test_postprocess_strips_expect_trace():
    raw = (
        "1.000 + expect\n"
        "1.001 Password:\n"
    )
    result = _postprocess(raw)
    assert "+ expect\n" not in result
    assert "Password:" in result

def test_postprocess_strips_expect_trace_with_args():
    raw = "1.000 + expect somefile.exp\n1.001 output\n"
    result = _postprocess(raw)
    assert "+ expect" not in result
    assert "output" in result

def test_postprocess_preserves_non_artifact_lines():
    raw = (
        "1.000 + echo hello\n"
        "1.001 hello\n"
    )
    result = _postprocess(raw)
    assert result == raw

def test_postprocess_custom_prefix():
    raw = (
        "1.000 ++ : SC mark mock\n"
        "1.001 ++ set +x\n"
        "1.002 ++ deploy\n"
    )
    result = _postprocess(raw, trace_prefix="++")
    assert "++ : SC mark mock" not in result
    assert "++ set +x" not in result
    assert "++ deploy" in result


def test_record_mock_directive_produces_command_trace(tmp_path):
    """SC mock directive in script produces a fake command trace in the .sc file."""
    script = tmp_path / "demo.sh"
    script.write_text(
        ": SC mock deploy <<'EOF'\nDeploying...\nEOF\n"
    )
    sc_path = tmp_path / "demo.sc"
    config = ScriptcastConfig()
    shell = shutil.which("bash")
    record(script, sc_path, config, shell)
    content = sc_path.read_text()
    assert "+ deploy" in content
    assert "Deploying..." in content
    assert "+ : SC mark mock" not in content
    assert "+ set +x" not in content
