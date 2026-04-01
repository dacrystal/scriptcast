# scriptcast/gif.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

TITLE_BAR_HEIGHT = 28
_TRAFFIC_LIGHTS = [
    (12, "#FF5F57"),  # red
    (32, "#FEBC2E"),  # yellow
    (52, "#28C840"),  # green
]
_TITLE_BAR_BG = "#1E1E1E"
_LIGHT_RADIUS = 6
_TITLE_COLOR = "#8A8A8A"


class AggNotFoundError(Exception):
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


def apply_frame_overlay(gif_path: Path, style: str = "macos", title: str = "") -> None:
    """Post-process a GIF to add a window chrome overlay. Modifies gif_path in place.

    Requires Pillow: pip install 'scriptcast[gif]'
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Pillow is required for frame overlay. "
            "Install with: pip install 'scriptcast[gif]'"
        )

    img = Image.open(gif_path)
    frames: list[Image.Image] = []
    durations: list[int] = []

    try:
        while True:
            frame = img.copy().convert("RGBA")
            durations.append(img.info.get("duration", 100))
            frames.append(_add_title_bar(frame, title))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    out = [f.convert("RGB").quantize(colors=256) for f in frames]
    out[0].save(
        gif_path,
        save_all=True,
        append_images=out[1:],
        loop=0,
        duration=durations,
        optimize=False,
    )


def _add_title_bar(frame: PILImage, title: str) -> PILImage:
    from PIL import Image, ImageDraw

    new_h = frame.height + TITLE_BAR_HEIGHT
    new_frame = Image.new("RGBA", (frame.width, new_h), _hex_rgba(_TITLE_BAR_BG))
    draw = ImageDraw.Draw(new_frame)

    y_center = TITLE_BAR_HEIGHT // 2
    for x, color in _TRAFFIC_LIGHTS:
        r = _LIGHT_RADIUS
        draw.ellipse([x - r, y_center - r, x + r, y_center + r], fill=_hex_rgba(color))

    if title:
        draw.text(
            (frame.width // 2, y_center),
            title,
            fill=_hex_rgba(_TITLE_COLOR),
            anchor="mm",
        )

    new_frame.paste(frame, (0, TITLE_BAR_HEIGHT))
    return new_frame


def _hex_rgba(hex_color: str) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
