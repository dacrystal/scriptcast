# scriptcast/gif.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class AggNotFoundError(RuntimeError):
    pass


def generate_gif(cast_path: str | Path) -> Path:
    """Convert a .cast file to .gif using agg. Returns the .gif path.

    Raises AggNotFoundError if agg is not installed.
    Install: https://github.com/asciinema/agg
    """
    agg = shutil.which("agg")
    if agg is None:
        raise AggNotFoundError(
            "agg not found. Install from: https://github.com/asciinema/agg"
        )
    cast_path = Path(cast_path)
    gif_path = cast_path.with_suffix(".gif")
    subprocess.run([agg, str(cast_path), str(gif_path)], check=True)
    return gif_path
