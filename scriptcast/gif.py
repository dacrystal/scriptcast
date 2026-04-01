# scriptcast/gif.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig


class AggNotFoundError(Exception):
    pass


def generate_gif(
    cast_path: str | Path, frame_config: FrameConfig | None = None
) -> Path:
    """Convert a .cast file to .gif using agg. Returns the .gif path.

    Raises AggNotFoundError if agg is not installed.
    Install: https://github.com/asciinema/agg

    If frame_config is provided, applies frame decoration after agg finishes.
    Requires Pillow: pip install 'scriptcast[gif]'
    """
    agg = shutil.which("agg")
    if agg is None:
        raise AggNotFoundError(
            "agg not found. Install from: https://github.com/asciinema/agg"
        )
    cast_path = Path(cast_path)
    gif_path = cast_path.with_suffix(".gif")
    subprocess.run([agg, str(cast_path), str(gif_path)], check=True)
    if frame_config is not None:
        from .frame import apply_frame
        apply_frame(gif_path, frame_config)
    return gif_path
