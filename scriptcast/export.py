# scriptcast/export.py
from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig

try:
    from PIL.Image import Image as PILImage
except ImportError:
    PILImage = object  # type: ignore[assignment,misc]

try:
    import cairosvg as _cairosvg
    _svg_available = True
except (ImportError, OSError):
    _cairosvg = None
    _svg_available = False

TITLE_BAR_HEIGHT = 28
_PACIFICO = Path(__file__).parent / "assets" / "fonts" / "Pacifico.ttf"
_WATERMARK_TEXT = "ScriptCast"
_TRAFFIC_LIGHTS = [
    (12, "#FF5F57", "#FF8C80"),  # red
    (32, "#FEBC2E", "#FFD466"),  # yellow
    (52, "#28C840", "#5DE87F"),  # green
]
_LIGHT_RADIUS = 6
_TITLE_COLOR = "#8A8A8A"
_WINDOW_BG = "#1E1E1E"


class AggNotFoundError(Exception):
    pass


def _hex_rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Parse a 6- or 8-character hex color string into an RGBA tuple."""
    h = hex_color.lstrip("#")
    if len(h) not in (6, 8):
        raise ValueError(f"_hex_rgba expects 6 or 8 hex digits, got {len(h)} in {hex_color!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def _split_rgba(hex_color: str) -> tuple[str, float]:
    """Return (#rrggbb, opacity_float) from a 6- or 8-char hex string."""
    h = hex_color.lstrip("#")
    if len(h) not in (6, 8):
        raise ValueError(f"_split_rgba expects 6 or 8 hex digits, got {len(h)} in {hex_color!r}")
    if len(h) == 8:
        return f"#{h[:6]}", int(h[6:8], 16) / 255.0
    return f"#{h}", 1.0


@dataclass
class Layout:
    content_w: int
    content_h: int
    half_bw: float
    window_x: float
    window_y: float
    window_w: int
    window_h: int
    content_x: int
    content_y: int
    canvas_w: int
    canvas_h: int
    title_bar_h: int
    title_cy: float


def _resolve_margin_sides(config: FrameConfig) -> tuple[int, int, int, int]:
    auto = 82 if config.background is not None else 0
    t = config.margin_top if config.margin_top is not None else auto
    r = config.margin_right if config.margin_right is not None else auto
    b = config.margin_bottom if config.margin_bottom is not None else auto
    l = config.margin_left if config.margin_left is not None else auto
    return (t, r, b, l)


def build_layout(content_w: int, content_h: int, config: FrameConfig) -> Layout:
    mt, mr, mb, ml = _resolve_margin_sides(config)
    half_bw = config.border_width / 2
    title_bar_h = TITLE_BAR_HEIGHT if config.frame_bar else 0

    window_w = config.padding_left + content_w + config.padding_right
    window_h = title_bar_h + config.padding_top + content_h + config.padding_bottom

    window_x = ml + half_bw
    window_y = mt + half_bw

    content_x = int(window_x + config.padding_left)
    content_y = int(window_y + title_bar_h + config.padding_top)

    canvas_w = int(ml + half_bw + window_w + half_bw + mr)
    canvas_h = int(mt + half_bw + window_h + half_bw + mb)

    title_cy = (window_y + half_bw + (title_bar_h - half_bw) / 2) if title_bar_h > 0 else 0.0

    return Layout(
        content_w=content_w,
        content_h=content_h,
        half_bw=half_bw,
        window_x=window_x,
        window_y=window_y,
        window_w=window_w,
        window_h=window_h,
        content_x=content_x,
        content_y=content_y,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        title_bar_h=title_bar_h,
        title_cy=title_cy,
    )


def _build_bg_shadow(layout: Layout, config: FrameConfig) -> PILImage:
    from PIL import Image, ImageDraw, ImageFilter

    # Background
    if config.background is None:
        base = Image.new("RGBA", (layout.canvas_w, layout.canvas_h), (0, 0, 0, 0))
    else:
        stops = [p.strip() for p in config.background.split(",")]
        if len(stops) == 1:
            base = Image.new("RGBA", (layout.canvas_w, layout.canvas_h), _hex_rgba(stops[0]))
        elif len(stops) == 2:
            color1 = _hex_rgba(stops[0])
            color2 = _hex_rgba(stops[1])
            base = Image.new("RGBA", (layout.canvas_w, layout.canvas_h))
            draw = ImageDraw.Draw(base)
            for x in range(layout.canvas_w):
                t = x / (layout.canvas_w - 1) if layout.canvas_w > 1 else 0.0
                col = tuple(int(color1[i] + t * (color2[i] - color1[i])) for i in range(4))
                draw.line([(x, 0), (x, layout.canvas_h - 1)], fill=col)
        else:
            raise ValueError(
                f"background gradient supports exactly 2 color stops, got {len(stops)}: "
                f"{config.background!r}"
            )

    if not config.shadow:
        return base

    # Drop shadow (PIL only — cairosvg blur is unreliable)
    r = config.shadow_radius
    offset_x = config.shadow_offset_x
    offset_y = config.shadow_offset_y
    shadow_color = _hex_rgba(config.shadow_color)

    wx = int(layout.window_x)
    wy = int(layout.window_y)
    ww = layout.window_w
    wh = layout.window_h

    pad = r * 2
    shadow_img = Image.new("RGBA", (ww + pad * 2, wh + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow_img)
    draw.rounded_rectangle(
        [pad, pad, pad + ww, pad + wh],
        radius=config.radius,
        fill=shadow_color,
    )
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(r))

    dest_x = wx - pad + offset_x
    dest_y = wy - pad + offset_y
    shadow_canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_canvas.paste(shadow_img, (dest_x, dest_y))
    return Image.alpha_composite(base, shadow_canvas)


def _draw_gradient_circle(
    img: PILImage,
    cx: int,
    cy: int,
    radius: int,
    base_color: str,
    highlight_color: str,
) -> None:
    from PIL import Image, ImageDraw

    steps = 8
    base = _hex_rgba(base_color)
    highlight = _hex_rgba(highlight_color)
    offset_x = int(radius * 0.20)

    for i in range(steps, 0, -1):
        t = i / steps
        r = int(base[0] * t + highlight[0] * (1 - t))
        g = int(base[1] * t + highlight[1] * (1 - t))
        b = int(base[2] * t + highlight[2] * (1 - t))
        circle_r = int(radius * (i + 1) / (steps + 1))
        shift = int((1 - t) * offset_x)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.ellipse(
            [cx - circle_r - shift, cy - circle_r - shift,
             cx + circle_r - shift, cy + circle_r - shift],
            fill=(r, g, b, 255),
        )
        img.paste(layer, (0, 0), layer)


def _build_chrome_pil(layout: Layout, config: FrameConfig) -> PILImage:
    from PIL import Image, ImageDraw

    chrome = Image.new("RGBA", (layout.canvas_w, layout.canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(chrome)

    wx = int(layout.window_x)
    wy = int(layout.window_y)
    ww = layout.window_w
    wh = layout.window_h
    r = config.radius

    # Window background (rounded rect)
    draw.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=r, fill=_hex_rgba(_WINDOW_BG))

    # Punch content area transparent — rounded bottom corners, straight top
    # (matches window's visual bottom corners; top is flat against title bar)
    r_punch = min(config.radius, layout.content_w // 2, layout.content_h // 2)
    punch_mask = Image.new("L", chrome.size, 0)
    punch_draw = ImageDraw.Draw(punch_mask)
    cx, cy = layout.content_x, layout.content_y
    cw, ch = layout.content_w, layout.content_h
    # Full rounded rect (rounds all corners)
    punch_draw.rounded_rectangle([cx, cy, cx + cw - 1, cy + ch - 1], radius=r_punch, fill=255)
    # Flatten top corners by overdrawing over the top r_punch rows
    if r_punch > 0:
        punch_draw.rectangle([cx, cy, cx + cw - 1, cy + r_punch], fill=255)
    # Apply: where punch_mask=255 (white), use transparent; where 0, keep chrome
    transparent_canvas = Image.new("RGBA", chrome.size, (0, 0, 0, 0))
    chrome = Image.composite(transparent_canvas, chrome, punch_mask)

    # Title bar
    if config.frame_bar and layout.title_bar_h > 0:
        clip = Image.new("L", chrome.size, 0)
        clip_draw = ImageDraw.Draw(clip)
        clip_draw.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=r, fill=255)
        clip_draw.rectangle([wx, wy + layout.title_bar_h, wx + ww, wy + wh], fill=0)
        titlebar_fill = Image.new("RGBA", chrome.size, _hex_rgba(config.frame_bar_color))
        chrome = Image.composite(titlebar_fill, chrome, clip)

        title_cy = int(layout.title_cy)

        if config.frame_bar_buttons:
            for x_off, base_color, highlight_color in _TRAFFIC_LIGHTS:
                _draw_gradient_circle(chrome, wx + x_off, title_cy,
                                      _LIGHT_RADIUS, base_color, highlight_color)

        if config.frame_bar_title:
            draw = ImageDraw.Draw(chrome)  # re-bind: chrome was replaced by composite
            draw.text(
                (wx + ww // 2, title_cy),
                config.frame_bar_title,
                fill=_hex_rgba(_TITLE_COLOR),
                anchor="mm",
            )

    # Border
    if config.border_width > 0:
        draw = ImageDraw.Draw(chrome)  # re-bind: chrome may have been replaced
        draw.rounded_rectangle(
            [wx, wy, wx + ww, wy + wh],
            radius=r,
            outline=_hex_rgba(config.border_color),
            width=config.border_width,
        )

    return chrome


def _build_svg(layout: Layout, config: FrameConfig) -> str:
    import html as _html

    wx = layout.window_x
    wy = layout.window_y
    ww = layout.window_w
    wh = layout.window_h
    cx = layout.content_x
    cy = layout.content_y
    cw = layout.content_w
    ch = layout.content_h
    r = config.radius
    canvas_w = layout.canvas_w
    canvas_h = layout.canvas_h
    title_cy = layout.title_cy

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {canvas_w} {canvas_h}"'
        f' height="{canvas_h}" width="{canvas_w}">'
    )
    parts.append("<defs>")

    # Radial gradients for traffic lights
    for i, (_xoff, base, highlight) in enumerate(_TRAFFIC_LIGHTS):
        parts.append(
            f'<radialGradient id="light-{i}" cx="35%" cy="30%" r="65%">'
            f'<stop offset="0%" stop-color="{highlight}"/>'
            f'<stop offset="100%" stop-color="{base}"/>'
            f"</radialGradient>"
        )

    # Mask that punches content area out of window bg
    parts.append('<mask id="content-hole">')
    parts.append(
        f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}"'
        f' rx="{r}" ry="{r}" fill="white"/>'
    )
    parts.append(
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" fill="black"/>'
    )
    parts.append("</mask>")

    # Clip path for title bar rounded top corners
    if config.frame_bar and layout.title_bar_h > 0:
        parts.append(
            f'<clipPath id="window-clip">'
            f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}"'
            f' rx="{r}" ry="{r}"/>'
            f"</clipPath>"
        )

    parts.append("</defs>")

    # Window background (with content hole)
    parts.append(
        f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}"'
        f' rx="{r}" ry="{r}" fill="{_WINDOW_BG}" mask="url(#content-hole)"/>'
    )

    # Title bar
    if config.frame_bar and layout.title_bar_h > 0:
        bc, ba = _split_rgba(config.frame_bar_color)
        parts.append(
            f'<rect x="{wx}" y="{wy}" width="{ww}" height="{layout.title_bar_h}"'
            f' fill="{bc}" fill-opacity="{ba:.3f}" clip-path="url(#window-clip)"/>'
        )

        if config.frame_bar_buttons:
            for i, (x_off, _base, _hl) in enumerate(_TRAFFIC_LIGHTS):
                lcx = wx + x_off
                parts.append(
                    f'<circle cx="{lcx}" cy="{title_cy}" r="{_LIGHT_RADIUS}"'
                    f' fill="url(#light-{i})"/>'
                )

        if config.frame_bar_title:
            tx = wx + ww // 2
            parts.append(
                f'<text x="{tx}" y="{title_cy}"'
                f' fill="{_TITLE_COLOR}"'
                f' font-family="system-ui,-apple-system,BlinkMacSystemFont,sans-serif"'
                f' font-size="12" text-anchor="middle" dominant-baseline="middle">'
                f"{_html.escape(config.frame_bar_title)}</text>"
            )

    # Border
    if config.border_width > 0:
        brc, bra = _split_rgba(config.border_color)
        parts.append(
            f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}"'
            f' rx="{r}" ry="{r}" fill="none"'
            f' stroke="{brc}" stroke-opacity="{bra:.3f}"'
            f' stroke-width="{config.border_width}"/>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _build_chrome_svg(layout: Layout, config: FrameConfig) -> PILImage:
    from PIL import Image

    svg_str = _build_svg(layout, config)
    png_bytes = _cairosvg.svg2png(bytestring=svg_str.encode())
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def _build_chrome(layout: Layout, config: FrameConfig) -> PILImage:
    if _svg_available:
        return _build_chrome_svg(layout, config)
    return _build_chrome_pil(layout, config)


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
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()

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


def _apply_scriptcast_watermark(base: PILImage, config: FrameConfig) -> PILImage:
    if not config.scriptcast_watermark:
        return base

    from PIL import ImageDraw, ImageFont

    result = base.copy()
    draw = ImageDraw.Draw(result)

    font_size = 14
    try:
        font = ImageFont.truetype(str(_PACIFICO), size=font_size)
    except (OSError, AttributeError):
        try:
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    x = base.width - 8
    y = base.height - 8
    draw.text((x + 1, y + 1), _WATERMARK_TEXT, fill=(0, 0, 0, 160), font=font, anchor="rb")
    draw.text((x, y), _WATERMARK_TEXT, fill=(255, 255, 255, 220), font=font, anchor="rb")
    return result


def apply_scriptcast_watermark(gif_path: Path, config: FrameConfig) -> None:
    """Overlay the ScriptCast brand watermark on an existing GIF in-place (no frame path).

    Used when --frame is not set but scriptcast_watermark is True.
    Requires Pillow: pip install 'scriptcast[gif]'
    """
    try:
        from PIL import Image
        from PIL.Image import Dither
    except ImportError:
        raise RuntimeError(
            "Pillow is required for watermark. "
            "Install with: pip install 'scriptcast[gif]'"
        )

    if not config.scriptcast_watermark:
        return

    raw_frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(gif_path) as img:
        try:
            while True:
                raw_frames.append(img.copy().convert("RGBA"))
                durations.append(img.info.get("duration", 100))
                img.seek(img.tell() + 1)
        except EOFError:
            pass

    out_frames = []
    for raw in raw_frames:
        with_wm = _apply_scriptcast_watermark(raw, config)
        out_frames.append(with_wm.convert("RGB").quantize(colors=256, dither=Dither.NONE))

    if not out_frames:
        return

    out_frames[0].save(
        gif_path,
        save_all=True,
        append_images=out_frames[1:],
        loop=0,
        duration=durations,
        optimize=False,
    )


def _chrome_colors(config: FrameConfig) -> list[tuple[int, int, int]]:
    """RGB colors that must be reserved in the GIF palette."""
    colors = [_hex_rgba(base)[:3] for _, base, _ in _TRAFFIC_LIGHTS]
    colors.append(_hex_rgba(_WINDOW_BG)[:3])
    colors.append(_hex_rgba(config.frame_bar_color)[:3])
    # Deduplicate while preserving order
    seen: set[tuple[int, int, int]] = set()
    result = []
    for c in colors:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _build_global_palette(
    template_rgb: PILImage,
    rgb_canvases: list[PILImage],
    config: FrameConfig,
    max_samples: int = 20,
) -> PILImage:
    from PIL import Image

    chrome_colors = _chrome_colors(config)
    n_chrome = len(chrome_colors)

    n = len(rgb_canvases)
    if max_samples <= 1 or n <= max_samples:
        indices = list(range(n))
    else:
        indices = [int(round(i * (n - 1) / (max_samples - 1))) for i in range(max_samples)]

    sampled = [rgb_canvases[i] for i in indices]
    w, h = template_rgb.size
    composite = Image.new("RGB", (w, h * (1 + len(sampled))))
    composite.paste(template_rgb, (0, 0))
    for idx, frame in enumerate(sampled):
        composite.paste(frame, (0, h * (idx + 1)))

    content_ref = composite.quantize(colors=256 - n_chrome)
    chrome_bytes = b"".join(bytes(c) for c in chrome_colors)
    raw_palette = content_ref.getpalette() or []
    content_bytes = bytes(raw_palette[: (256 - n_chrome) * 3])
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(chrome_bytes + content_bytes)
    return palette_img


def apply_export(gif_path: Path, config: FrameConfig, format: str = "gif") -> None:
    """Post-process a GIF in-place: apply background, shadow, chrome, and watermarks.

    format: "gif" writes .gif (quantized 256 colours); "apng" writes .png (full RGBA).
    Requires Pillow: pip install 'scriptcast[gif]'
    """
    try:
        from PIL import Image
        from PIL.Image import Dither
    except ImportError:
        raise RuntimeError(
            "Pillow is required for frame overlay. "
            "Install with: pip install 'scriptcast[gif]'"
        )

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

    if not raw_frames:
        return

    content_w, content_h = raw_frames[0].size
    layout = build_layout(content_w, content_h, config)
    bg_shadow = _build_bg_shadow(layout, config)
    chrome = _build_chrome(layout, config)

    output_path = gif_path if format == "gif" else gif_path.with_suffix(".png")

    rgba_frames = []
    for raw in raw_frames:
        canvas = bg_shadow.copy()
        canvas.paste(raw, (layout.content_x, layout.content_y))
        canvas = Image.alpha_composite(canvas, chrome)
        canvas = _apply_watermark(canvas, config)
        canvas = _apply_scriptcast_watermark(canvas, config)
        rgba_frames.append(canvas)

    if format == "apng":
        rgba_frames[0].save(
            output_path,
            format="PNG",
            save_all=True,
            append_images=rgba_frames[1:],
            loop=0,
            duration=durations,
        )
    else:
        template_rgb = Image.alpha_composite(bg_shadow, chrome).convert("RGB")
        rgb_canvases = [c.convert("RGB") for c in rgba_frames]
        palette_ref = _build_global_palette(template_rgb, rgb_canvases, config)
        out_frames = [
            f.quantize(palette=palette_ref, dither=Dither.NONE)
            for f in rgb_canvases
        ]
        out_frames[0].save(
            output_path,
            save_all=True,
            append_images=out_frames[1:],
            loop=0,
            duration=durations,
            optimize=False,
        )


def generate_export(
    cast_path: str | Path,
    frame_config: FrameConfig | None = None,
    format: str = "gif",
) -> Path:
    """Convert a .cast file to GIF or APNG using agg, then apply frame if configured.

    Raises AggNotFoundError if agg is not installed.
    Install: https://github.com/asciinema/agg

    format: "gif" (default) writes .gif; "apng" writes .png (full RGBA).
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
        apply_export(gif_path, frame_config, format=format)
        output_path = gif_path if format == "gif" else gif_path.with_suffix(".png")
    else:
        output_path = gif_path

    return output_path
