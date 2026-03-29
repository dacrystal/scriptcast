# tests/test_gif.py
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from scriptcast.gif import generate_gif, AggNotFoundError


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
