# tests/test_cli.py
from pathlib import Path

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


def test_gif_command_removed():
    """The gif command should be completely removed."""
    assert "gif" not in cli.commands


def test_export_removed_flags_rejected(tmp_path):
    """Flags removed from export: theme-configurable props should not exist."""
    import json
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    sc = tmp_path / "demo.sc"
    sc.write_text(
        json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"
    )
    runner = CliRunner()
    for flag in ["--frame-bar-title", "--frame-bar-color", "--watermark"]:
        result = runner.invoke(cli, ["export", str(sc), flag, "x"])
        assert result.exit_code != 0, f"{flag} should be rejected"
    result = runner.invoke(cli, ["export", str(sc), "--no-frame-bar"])
    assert result.exit_code != 0, "--no-frame-bar should be rejected"
    result = runner.invoke(cli, ["export", str(sc), "--no-frame-bar-buttons"])
    assert result.exit_code != 0, "--no-frame-bar-buttons should be rejected"


def test_title_flag_rejected_on_generate(tmp_path):
    import json
    sc = tmp_path / "demo.sc"
    sc.write_text(json.dumps({"directive-prefix": "SC"}) + "\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", str(sc), "--title"])
    assert result.exit_code != 0


def test_title_flag_rejected_on_root(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("echo hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["--title", str(script)])
    assert result.exit_code != 0


def test_export_cast_input_accepted(tmp_path):
    """export accepts a .cast file directly, skipping generate step."""
    import json
    from unittest.mock import patch
    cast = tmp_path / "demo.cast"
    cast.write_text(json.dumps({"version": 2, "width": 80, "height": 24}) + "\n")
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["export", str(cast), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_export_sh_input_runs_full_pipeline(tmp_path):
    """export accepts a .sh file and runs record → generate → export."""
    from unittest.mock import patch, ANY
    from scriptcast.config import ScriptcastConfig
    import json
    sh = tmp_path / "demo.sh"
    sh.write_text("echo hello\n")
    cast = tmp_path / "demo.cast"
    cast.write_text(json.dumps({"version": 2}) + "\n")
    runner = CliRunner()
    with patch("scriptcast.__main__.do_record") as mock_record, \
         patch("scriptcast.__main__.generate_from_sc", return_value=[cast]), \
         patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["export", str(sh), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    mock_record.assert_called_once_with(
        sh,
        tmp_path / "demo.sc",
        ScriptcastConfig(directive_prefix="SC", trace_prefix="+"),
        ANY,
    )


def test_export_unsupported_extension_errors(tmp_path):
    """export rejects files with unsupported extensions."""
    f = tmp_path / "demo.txt"
    f.write_text("hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["export", str(f)])
    assert result.exit_code != 0
    assert "Unsupported" in result.output


def test_install_command_exists():
    from scriptcast.__main__ import cli
    assert "install" in cli.commands


def test_install_command_has_prefix_option():
    from scriptcast.__main__ import cli
    param_names = [p.name for p in cli.commands["install"].params]
    assert "prefix" in param_names


def test_export_default_format_is_png():
    """export --format default is 'png', not 'gif'."""
    from scriptcast.__main__ import export
    param = next(p for p in export.params if p.name == "output_format")
    assert param.default == "png"


def test_export_format_png_accepted(tmp_path):
    """--format png is a valid choice."""
    import json
    from unittest.mock import patch
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    cast = tmp_path / "demo.cast"
    cast.write_text(json.dumps({"version": 2, "width": 80, "height": 24}) + "\n")
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["export", str(cast), "--format", "png"])
    assert result.exit_code == 0, result.output


def test_export_format_apng_rejected(tmp_path):
    """--format apng is no longer a valid choice."""
    import json
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    cast = tmp_path / "demo.cast"
    cast.write_text(json.dumps({"version": 2, "width": 80, "height": 24}) + "\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["export", str(cast), "--format", "apng"])
    assert result.exit_code != 0
    assert "apng" in result.output or "invalid" in result.output.lower()


def test_install_downloads_agg_and_fonts(tmp_path):
    import io, json, zipfile
    from unittest.mock import MagicMock, patch

    # Build a fake JetBrains Mono zip with one TTF
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("fonts/ttf/JetBrainsMono-Regular.ttf", b"fake-ttf-data")
    zip_bytes = buf.getvalue()

    def fake_urlretrieve(url, dest):
        dest = Path(dest)
        if "agg" in url:
            dest.write_bytes(b"fake-agg-binary")
        else:
            dest.write_bytes(zip_bytes)

    fake_release = json.dumps({"assets": [
        {"name": "JetBrainsMono-2.304.zip",
         "browser_download_url": "https://example.com/JetBrainsMono-2.304.zip"},
    ]}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_release
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    runner = CliRunner()
    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        result = runner.invoke(cli, ["install", "--prefix", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".agg-real").exists()
    assert (tmp_path / "agg").exists()
    agg_text = (tmp_path / "agg").read_text()
    assert "fonts" in agg_text
    assert "JetBrains Mono" in agg_text
    assert (tmp_path / "fonts" / "JetBrainsMono-Regular.ttf").exists()
