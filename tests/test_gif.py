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


def _make_tiny_gif(path, width=40, height=20):
    """Create a minimal 2-frame GIF for testing."""
    from PIL import Image
    frame1 = Image.new("RGB", (width, height), (30, 30, 30))
    frame2 = Image.new("RGB", (width, height), (40, 40, 40))
    q1 = frame1.quantize(colors=256)
    q2 = frame2.quantize(colors=256)
    q1.save(path, save_all=True, append_images=[q2], duration=100, loop=0)


def test_apply_frame_overlay_increases_height(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.gif import TITLE_BAR_HEIGHT, apply_frame_overlay

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)
    apply_frame_overlay(gif_path, style="macos")

    result = Image.open(gif_path)
    assert result.height == 20 + TITLE_BAR_HEIGHT


def test_apply_frame_overlay_preserves_width(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.gif import apply_frame_overlay

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)
    apply_frame_overlay(gif_path, style="macos")

    result = Image.open(gif_path)
    assert result.width == 40


def test_apply_frame_overlay_missing_pillow(tmp_path, monkeypatch):
    import builtins
    import sys

    from scriptcast.gif import apply_frame_overlay

    gif_path = tmp_path / "test.gif"
    gif_path.write_bytes(b"GIF89a")

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("PIL"):
            raise ImportError("No module named 'PIL'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    for key in list(sys.modules):
        if key.startswith("PIL"):
            monkeypatch.delitem(sys.modules, key)

    with pytest.raises(RuntimeError, match="Pillow"):
        apply_frame_overlay(gif_path)


def test_gif_command_frame_option(tmp_path):
    """--frame macos calls apply_frame_overlay after each gif is generated."""
    import json
    from unittest.mock import patch

    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_content = (
        json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"
    )
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc_content)
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif):
            with patch("scriptcast.__main__.apply_frame_overlay") as mock_overlay:
                result = runner.invoke(
                    cli,
                    [
                        "gif", str(sc_file), "--output-dir", str(tmp_path),
                        "--frame", "macos", "--frame-title", "Demo",
                    ],
                )
    assert result.exit_code == 0, result.output
    mock_overlay.assert_called_once_with(fake_gif, style="macos", title="Demo")


def test_gif_command_no_frame_skips_overlay(tmp_path):
    """Without --frame, apply_frame_overlay is not called."""
    import json
    from unittest.mock import patch

    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_content = (
        json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"
    )
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc_content)
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif):
            with patch("scriptcast.__main__.apply_frame_overlay") as mock_overlay:
                result = runner.invoke(
                    cli,
                    ["gif", str(sc_file), "--output-dir", str(tmp_path)],
                )
    assert result.exit_code == 0, result.output
    mock_overlay.assert_not_called()


def test_gif_command_frame_overlay_error_is_clean(tmp_path):
    """RuntimeError from apply_frame_overlay (e.g. missing Pillow) gives a clean CLI error."""
    import json
    from unittest.mock import patch

    from click.testing import CliRunner

    from scriptcast.__main__ import cli

    sc_content = (
        json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"}) + "\n"
    )
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc_content)
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_gif", return_value=fake_gif):
            with patch(
                "scriptcast.__main__.apply_frame_overlay",
                side_effect=RuntimeError("Pillow not installed"),
            ):
                result = runner.invoke(
                    cli,
                    ["gif", str(sc_file), "--output-dir", str(tmp_path), "--frame", "macos"],
                )
    assert result.exit_code == 1
    assert "Pillow not installed" in result.output
