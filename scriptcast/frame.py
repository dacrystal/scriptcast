# scriptcast/frame.py
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig

try:
    from PIL.Image import Image as PILImage
except ImportError:  # Pillow not installed — only used at runtime inside functions
    PILImage = object  # type: ignore[assignment,misc]

TITLE_BAR_HEIGHT = 28
_TRAFFIC_LIGHTS = [
    (12, "#FF5F57"),  # red
    (32, "#FEBC2E"),  # yellow
    (52, "#28C840"),  # green
]
_LIGHT_RADIUS = 6
_TITLE_COLOR = "#8A8A8A"
_WINDOW_BG = "#1E1E1E"


def _hex_rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Parse a 6- or 8-character hex color string into an RGBA tuple."""
    h = hex_color.lstrip("#")
    if len(h) not in (6, 8):
        raise ValueError(f"_hex_rgba expects 6 or 8 hex digits, got {len(h)} in {hex_color!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def _resolve_margins(config: FrameConfig) -> tuple[int, int]:
    """Resolve None margins to their automatic default based on whether a background is set."""
    auto = 82 if config.background is not None else 0
    mx = config.margin_x if config.margin_x is not None else auto
    my = config.margin_y if config.margin_y is not None else auto
    return mx, my


def _build_background(canvas_w: int, canvas_h: int, config: FrameConfig) -> PILImage:
    from PIL import Image, ImageDraw

    if config.background is None:
        return Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    parts = [p.strip() for p in config.background.split(",")]
    if len(parts) == 1:
        return Image.new("RGBA", (canvas_w, canvas_h), _hex_rgba(parts[0]))
    if len(parts) > 2:
        raise ValueError(
            f"background gradient supports exactly 2 color stops, got {len(parts)}: "
            f"{config.background!r}"
        )

    # Two-stop horizontal gradient
    color1 = _hex_rgba(parts[0])
    color2 = _hex_rgba(parts[1])
    img = Image.new("RGBA", (canvas_w, canvas_h))
    draw = ImageDraw.Draw(img)
    for x in range(canvas_w):
        t = x / (canvas_w - 1) if canvas_w > 1 else 0.0
        col = tuple(int(color1[i] + t * (color2[i] - color1[i])) for i in range(4))
        draw.line([(x, 0), (x, canvas_h - 1)], fill=col)
    return img


def _apply_shadow(
    base: PILImage,
    window_x: int,
    window_y: int,
    window_w: int,
    window_h: int,
    config: FrameConfig,
) -> PILImage:
    if not config.shadow:
        return base

    from PIL import Image, ImageDraw, ImageFilter

    r = config.shadow_radius
    offset_y = config.shadow_offset_y
    shadow_color = _hex_rgba(config.shadow_color)

    # Pad the shadow pixmap so blur can spread outside the rect edges
    pad = r * 2
    shadow_img = Image.new("RGBA", (window_w + pad * 2, window_h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow_img)
    draw.rounded_rectangle(
        [pad, pad, pad + window_w, pad + window_h],
        radius=config.radius,
        fill=shadow_color,
    )
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(r))

    result = base.copy()
    dest_x = window_x - pad
    dest_y = window_y - pad + offset_y
    result.paste(shadow_img, (dest_x, dest_y), shadow_img)
    return result


def _apply_window_rect(
    base: PILImage,
    window_x: int,
    window_y: int,
    window_w: int,
    window_h: int,
    config: FrameConfig,
) -> PILImage:
    from PIL import ImageDraw

    result = base.copy()
    draw = ImageDraw.Draw(result)
    box = [window_x, window_y, window_x + window_w, window_y + window_h]

    draw.rounded_rectangle(box, radius=config.radius, fill=_hex_rgba(_WINDOW_BG))

    if config.border_width > 0:
        draw.rounded_rectangle(
            box,
            radius=config.radius,
            outline=_hex_rgba(config.border_color),
            width=config.border_width,
        )
    return result


def _apply_title_bar(
    base: PILImage,
    window_x: int,
    window_y: int,
    window_w: int,
    config: FrameConfig,
) -> PILImage:
    from PIL import ImageDraw

    result = base.copy()
    draw = ImageDraw.Draw(result)
    y_center = window_y + TITLE_BAR_HEIGHT // 2

    for light_x, color in _TRAFFIC_LIGHTS:
        cx = window_x + light_x
        r = _LIGHT_RADIUS
        draw.ellipse([cx - r, y_center - r, cx + r, y_center + r], fill=_hex_rgba(color))

    if config.title:
        draw.text(
            (window_x + window_w // 2, y_center),
            config.title,
            fill=_hex_rgba(_TITLE_COLOR),
            anchor="mm",
        )
    return result


def _apply_watermark(base: PILImage, config: FrameConfig) -> PILImage:
    if config.watermark is None:
        return base

    from PIL import ImageDraw, ImageFont

    result = base.copy()
    draw = ImageDraw.Draw(result)

    font_size = (
        config.watermark_size
        if config.watermark_size is not None
        else int(max(20, min(30, base.width * 0.11)))
    )

    try:
        font = ImageFont.load_default(size=font_size)  # Pillow >= 10.0
    except TypeError:
        font = ImageFont.load_default()                 # Pillow 9.x

    x = base.width // 2
    y = base.height - 22 - font_size // 2
    draw.text(
        (x, y),
        config.watermark,
        fill=_hex_rgba(config.watermark_color),
        font=font,
        anchor="mm",
    )
    return result


def apply_frame(gif_path: Path, config: FrameConfig) -> None:
    """Post-process a GIF in-place: add background, shadow, window chrome, and optional watermark.

    Requires Pillow: pip install 'scriptcast[gif]'
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Pillow is required for frame overlay. "
            "Install with: pip install 'scriptcast[gif]'"
        )

    margin_x, margin_y = _resolve_margins(config)

    img = Image.open(gif_path)
    raw_frames: list[Image.Image] = []
    durations: list[int] = []
    try:
        while True:
            raw_frames.append(img.copy().convert("RGBA"))
            durations.append(img.info.get("duration", 100))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    frame_w, frame_h = raw_frames[0].size
    window_w = frame_w + 2 * config.padding_x
    window_h = frame_h + 2 * config.padding_y + TITLE_BAR_HEIGHT
    canvas_w = window_w + 2 * margin_x
    canvas_h = window_h + 2 * margin_y
    window_x = margin_x
    window_y = margin_y
    content_x = window_x + config.padding_x
    content_y = window_y + TITLE_BAR_HEIGHT + config.padding_y

    # Build template — identical for every frame
    template = _build_background(canvas_w, canvas_h, config)
    template = _apply_shadow(template, window_x, window_y, window_w, window_h, config)
    template = _apply_window_rect(template, window_x, window_y, window_w, window_h, config)
    template = _apply_title_bar(template, window_x, window_y, window_w, config)
    template = _apply_watermark(template, config)

    out_frames = []
    for raw in raw_frames:
        canvas = template.copy()
        canvas.paste(raw, (content_x, content_y))
        out_frames.append(canvas.convert("RGB").quantize(colors=256))

    out_frames[0].save(
        gif_path,
        save_all=True,
        append_images=out_frames[1:],
        loop=0,
        duration=durations,
        optimize=False,
    )
