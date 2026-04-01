# tests/test_gif.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptcast.gif import AggNotFoundError, generate_gif


def test_generate_gif_calls_agg(tmp_path):
    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("shutil.which", return_value="/usr/bin/agg"):
            result = generate_gif(cast_file)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "agg" in args[0]
    assert str(cast_file) in args
    assert result == tmp_path / "scene.gif"


def test_missing_agg_raises():
    with patch("shutil.which", return_value=None):
        with pytest.raises(AggNotFoundError, match="agg"):
            generate_gif(Path("scene.cast"))


def test_generate_gif_calls_apply_frame_when_config_provided(tmp_path):
    """When frame_config is passed, generate_gif calls frame.apply_frame."""
    from scriptcast.config import FrameConfig

    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')
    gif_file = tmp_path / "scene.gif"
    config = FrameConfig()

    def fake_run(*args: object, **kwargs: object) -> MagicMock:
        gif_file.write_bytes(b"GIF89a")
        return MagicMock(returncode=0)

    with patch("shutil.which", return_value="/usr/bin/agg"):
        with patch("subprocess.run", side_effect=fake_run):
            with patch("scriptcast.frame.apply_frame") as mock_apply:
                generate_gif(cast_file, config)

    mock_apply.assert_called_once_with(gif_file, config)


def test_generate_gif_skips_apply_frame_when_no_config(tmp_path):
    """Without frame_config, frame.apply_frame is never called."""
    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')

    with patch("shutil.which", return_value="/usr/bin/agg"):
        with patch("subprocess.run"):
            with patch("scriptcast.frame.apply_frame") as mock_apply:
                try:
                    generate_gif(cast_file)
                except Exception:
                    pass

    mock_apply.assert_not_called()


def _sc_content() -> str:
    import json
    return json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"


def test_gif_command_frame_passes_config(tmp_path):
    """--frame builds a FrameConfig and passes it to generate_gif."""
    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif) as mock_gif:
            result = runner.invoke(
                cli,
                ["gif", str(sc_file), "--output-dir", str(tmp_path),
                 "--frame", "--title", "Demo", "--background", "#1a1a2e"],
            )
    assert result.exit_code == 0, result.output
    frame_config = mock_gif.call_args[0][1]
    assert frame_config is not None
    assert frame_config.title == "Demo"
    assert frame_config.background == "#1a1a2e"
    assert frame_config.shadow is True  # default when --frame


def test_gif_command_no_frame_passes_none(tmp_path):
    """Without --frame, generate_gif receives frame_config=None."""
    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif) as mock_gif:
            result = runner.invoke(cli, ["gif", str(sc_file), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert mock_gif.call_args[0][1] is None


def test_gif_command_no_shadow_flag(tmp_path):
    """--no-shadow sets shadow=False on FrameConfig."""
    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif) as mock_gif:
            result = runner.invoke(
                cli,
                ["gif", str(sc_file), "--output-dir", str(tmp_path), "--frame", "--no-shadow"],
            )
    assert result.exit_code == 0, result.output
    assert mock_gif.call_args[0][1].shadow is False


def test_gif_command_frame_error_is_clean(tmp_path):
    """RuntimeError from generate_gif (e.g. missing Pillow) gives a clean CLI error."""
    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch(
            "scriptcast.__main__.generate_gif",
            side_effect=RuntimeError("Pillow not installed"),
        ):
            result = runner.invoke(
                cli,
                ["gif", str(sc_file), "--output-dir", str(tmp_path), "--frame"],
            )
    assert result.exit_code == 1
    assert "Pillow not installed" in result.output
