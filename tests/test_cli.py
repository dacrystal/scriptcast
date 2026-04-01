# tests/test_cli.py
from click.testing import CliRunner

from scriptcast.__main__ import cli


def test_record_subcommand(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["record", str(script), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.sc").exists()


def test_generate_subcommand(tmp_path):
    import json as _json
    sc = tmp_path / "demo.sc"
    sc.write_text(
        _json.dumps({"version": 1, "shell": "bash", "directive-prefix": "SC"}) + "\n"
        + _json.dumps([1.0, "directive", "scene main"]) + "\n"
        + _json.dumps([1.1, "cmd", "echo hi"]) + "\n"
        + _json.dumps([1.2, "output", "hi"]) + "\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        cli, ["generate", str(sc), "--output-dir", str(tmp_path), "--split-scenes"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "main.cast").exists()


def test_end_to_end(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text(": SC scene demo\necho hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(script)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()


def test_missing_script_errors():
    runner = CliRunner()
    result = runner.invoke(cli, ["record", "nonexistent.sh"])
    assert result.exit_code != 0


def test_directive_prefix_flag(tmp_path):
    import json as _json
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["record", str(script), "--directive-prefix", "DEMO", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    header = _json.loads((tmp_path / "demo.sc").read_text().splitlines()[0])
    assert header["directive-prefix"] == "DEMO"


def test_split_scenes_flag_produces_per_scene_files(tmp_path):
    """--split-scenes produces one .cast per scene (old behavior)."""
    script = tmp_path / "demo.sh"
    script.write_text(
        ": SC set width 80\n: SC set height 24\n"
        ": SC scene alpha\necho a\n"
        ": SC scene beta\necho b\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        cli, ["--output-dir", str(tmp_path), "--split-scenes", str(script)]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "alpha.cast").exists()
    assert (tmp_path / "beta.cast").exists()

def test_default_single_cast_output(tmp_path):
    """Default (no --split-scenes) produces a single .cast named after the script."""
    script = tmp_path / "demo.sh"
    script.write_text(
        ": SC set width 80\n: SC set height 24\n"
        ": SC scene alpha\necho a\n"
        ": SC scene beta\necho b\n"
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(script)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()
    assert not (tmp_path / "alpha.cast").exists()


def test_options_before_script_path(tmp_path):
    """Options placed before the script path are parsed correctly."""
    script = tmp_path / "demo.sh"
    script.write_text(": SC scene demo\necho hello\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--output-dir", str(tmp_path), "--split-scenes", str(script)],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()


def test_no_args_prints_help():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_nonexistent_script_errors(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [str(tmp_path / "nope.sh")])
    assert result.exit_code != 0


def test_extra_args_after_script_errors(tmp_path):
    """Extra positional args after the script path produce a clear error."""
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, [str(script), "extra"])
    assert result.exit_code != 0
    assert "Unexpected arguments" in result.output
