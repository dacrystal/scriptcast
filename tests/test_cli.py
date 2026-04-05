# tests/test_cli.py
import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from scriptcast.__main__ import cli


# ── helpers ────────────────────────────────────────────────────────────────

def _minimal_cast(tmp_path: Path, name: str = "demo") -> Path:
    cast = tmp_path / f"{name}.cast"
    cast.write_text(json.dumps({"version": 2, "width": 80, "height": 24}) + "\n")
    return cast


def _minimal_sc(tmp_path: Path, name: str = "demo") -> Path:
    sc = tmp_path / f"{name}.sc"
    sc.write_text(
        json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"
    )
    return sc


def _sh(tmp_path: Path, content: str = ": SC scene demo\necho hello\n") -> Path:
    script = tmp_path / "demo.sh"
    script.write_text(content)
    return script


# ── no-args / help ─────────────────────────────────────────────────────────

def test_no_args_prints_help():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


# ── error cases ────────────────────────────────────────────────────────────

def test_nonexistent_file_errors(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [str(tmp_path / "nope.sh")])
    assert result.exit_code != 0


def test_unsupported_extension_errors(tmp_path):
    f = tmp_path / "demo.txt"
    f.write_text("hello\n")
    runner = CliRunner()
    result = runner.invoke(cli, [str(f)])
    assert result.exit_code != 0
    assert "Unsupported" in result.output


def test_extra_args_after_input_errors(tmp_path):
    script = _sh(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [str(script), "extra"])
    assert result.exit_code != 0
    assert "Unexpected" in result.output


def test_cast_input_with_no_export_errors(tmp_path):
    cast = _minimal_cast(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["--no-export", str(cast)])
    assert result.exit_code != 0


# ── .sh input (full pipeline) ──────────────────────────────────────────────

def test_sh_input_end_to_end(tmp_path):
    """scriptcast demo.sh records, generates, exports."""
    script = _sh(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(script)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()


def test_sh_input_no_export_produces_cast(tmp_path):
    """scriptcast demo.sh --no-export produces .cast but no export."""
    script = _sh(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), "--no-export", str(script)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()


def test_sh_input_split_scenes(tmp_path):
    script = _sh(tmp_path, content=(
        ": SC scene alpha\necho a\n"
        ": SC scene beta\necho b\n"
    ))
    runner = CliRunner()
    result = runner.invoke(
        cli, ["--output-dir", str(tmp_path), "--split-scenes", str(script)]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "alpha.cast").exists()
    assert (tmp_path / "beta.cast").exists()


def test_sh_input_single_cast_default(tmp_path):
    script = _sh(tmp_path, content=(
        ": SC scene alpha\necho a\n"
        ": SC scene beta\necho b\n"
    ))
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(script)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()
    assert not (tmp_path / "alpha.cast").exists()


def test_sh_input_directive_prefix_stored_in_sc(tmp_path):
    script = _sh(tmp_path, content="echo hello\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--directive-prefix", "DEMO", "--output-dir", str(tmp_path), "--no-export", str(script)],
    )
    assert result.exit_code == 0, result.output
    header = json.loads((tmp_path / "demo.sc").read_text().splitlines()[0])
    assert header["directive-prefix"] == "DEMO"


# ── .sc input ──────────────────────────────────────────────────────────────

def test_sc_input_generates_and_exports(tmp_path):
    sc = _minimal_sc(tmp_path)
    cast = tmp_path / "demo.cast"
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast) as mock_exp, \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(sc)])
    assert result.exit_code == 0, result.output
    mock_exp.assert_called_once()


def test_sc_input_no_export_produces_cast(tmp_path):
    sc = _minimal_sc(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["--output-dir", str(tmp_path), "--no-export", str(sc)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo.cast").exists()


# ── .cast input ────────────────────────────────────────────────────────────

def test_cast_input_exports(tmp_path):
    cast = _minimal_cast(tmp_path)
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["--output-dir", str(tmp_path), str(cast)])
    assert result.exit_code == 0, result.output


# ── format flag ────────────────────────────────────────────────────────────

def test_format_png_accepted(tmp_path):
    cast = _minimal_cast(tmp_path)
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["--format", "png", str(cast)])
    assert result.exit_code == 0, result.output


def test_format_gif_accepted(tmp_path):
    cast = _minimal_cast(tmp_path)
    runner = CliRunner()
    with patch("scriptcast.__main__.generate_export", return_value=cast), \
         patch("scriptcast.__main__.apply_scriptcast_watermark"):
        result = runner.invoke(cli, ["--format", "gif", str(cast)])
    assert result.exit_code == 0, result.output


def test_format_apng_rejected(tmp_path):
    cast = _minimal_cast(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["--format", "apng", str(cast)])
    assert result.exit_code != 0


# ── install subcommand ─────────────────────────────────────────────────────

def test_install_command_exists():
    assert "install" in cli.commands


def test_install_command_has_prefix_option():
    param_names = [p.name for p in cli.commands["install"].params]
    assert "prefix" in param_names


def test_install_downloads_agg_and_fonts(tmp_path):
    import io, zipfile
    from unittest.mock import MagicMock

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
    assert (tmp_path / "fonts" / "JetBrainsMono-Regular.ttf").exists()


# ── removed subcommands ────────────────────────────────────────────────────

def test_record_subcommand_removed():
    assert "record" not in cli.commands


def test_generate_subcommand_removed():
    assert "generate" not in cli.commands


def test_export_subcommand_removed():
    assert "export" not in cli.commands
