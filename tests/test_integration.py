# tests/test_integration.py
"""Integration test using examples/basic.sh as a real end-to-end fixture."""
import json
from pathlib import Path
from click.testing import CliRunner
from scriptcast.__main__ import cli

BASIC_SCRIPT = Path(__file__).parent.parent / "examples" / "basic.sh"


def test_basic_example_end_to_end(tmp_path):
    """examples/basic.sh produces a single basic.cast with valid asciinema v2 header."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(BASIC_SCRIPT), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    cast_file = tmp_path / "basic.cast"
    assert cast_file.exists()

    lines = cast_file.read_text().splitlines()
    header = json.loads(lines[0])
    assert header["version"] == 2
    assert header["width"] == 80
    assert header["height"] == 24


def test_basic_example_end_to_end_split_mode(tmp_path):
    """--split-scenes produces one .cast per scene."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [str(BASIC_SCRIPT), "--output-dir", str(tmp_path), "--split-scenes"],
    )
    assert result.exit_code == 0, result.output

    cast_files = sorted(tmp_path.glob("*.cast"))
    names = {f.stem for f in cast_files}
    assert names == {"intro", "mock", "filter"}


def test_basic_example_record_stage(tmp_path):
    """`scriptcast record` on basic.sh produces a .sc file with the right header."""
    runner = CliRunner()
    result = runner.invoke(cli, ["record", str(BASIC_SCRIPT), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    sc_file = tmp_path / "basic.sc"
    assert sc_file.exists()
    content = sc_file.read_text()
    assert "#shell=" in content
    assert "#trace-prefix=+" in content
    assert "#directive-prefix=SC" in content


def test_basic_example_mock_scene_shows_command(tmp_path):
    """`basic.cast` contains the mock deploy command as a typed command trace."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(BASIC_SCRIPT), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    cast_file = tmp_path / "basic.cast"
    content = cast_file.read_text()
    # "deploy" should appear as typed output (the mock command)
    all_text = "".join(
        json.loads(l)[2]
        for l in content.splitlines()[1:]
        if l.strip()
    )
    assert "deploy" in all_text
    assert "Deploying to production" in all_text


def test_basic_example_filter_applied(tmp_path):
    """`basic.cast` must not contain the raw working directory path."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(BASIC_SCRIPT), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output

    cast_file = tmp_path / "basic.cast"
    assert cast_file.exists()
    content = cast_file.read_text()
    assert "/workspaces/scriptcast" not in content
    assert "<project>" in content
