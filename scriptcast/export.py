# scriptcast/export.py
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from PIL.Image import Dither

from .config import ThemeConfig

TITLE_BAR_HEIGHT = 28
_PACIFICO = Path(__file__).parent / "assets" / "fonts" / "Pacifico.ttf"
_DM_SANS = Path(__file__).parent / "assets" / "fonts" / "DMSans-Regular.ttf"
_WATERMARK_TEXT = "ScriptCast"
_TRAFFIC_LIGHTS = [
    (12, "#FF5F57", "#FF8C80"),  # red
    (32, "#FEBC2E", "#FFD466"),  # yellow
    (52, "#28C840", "#5DE87F"),  # green
]
_LIGHT_RADIUS = 6
_TITLE_COLOR = "#8A8A8A"


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


def _resolve_margin_sides(config: ThemeConfig) -> tuple[int, int, int, int]:
    auto = 82 if config.background is not None else 0
    sides = (config.margin_top, config.margin_right, config.margin_bottom, config.margin_left)
    return tuple(s if s is not None else auto for s in sides)  # type: ignore[return-value]


def build_layout(content_w: int, content_h: int, config: ThemeConfig) -> Layout:
    mt, mr, mb, ml = _resolve_margin_sides(config)
    half_bw = config.border_width / 2
    title_bar_h = TITLE_BAR_HEIGHT if config.frame_bar else 0

    window_w = content_w + config.border_width * 2
    window_h = title_bar_h + content_h + config.border_width

    window_x = ml + half_bw
    window_y = mt + half_bw

    content_x = int(window_x) + config.border_width
    content_y = int(window_y + title_bar_h)

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


def _build_bg_shadow(layout: Layout, config: ThemeConfig) -> Image.Image:
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


def _preprocess_frames(
    frames: list,
    config: ThemeConfig,
) -> tuple:
    """Detect terminal bg colour and bake padding into every content frame.

    Returns (padded_frames, terminal_bg) where terminal_bg is an RGB triple.
    Alpha-composites frame onto a terminal_bg canvas so transparent corner pixels
    show bg, not garbage palette RGB values.
    """
    first = frames[0].convert("RGBA")
    w, h = first.size
    terminal_bg: tuple[int, int, int] = first.getpixel((w // 2, 1))[:3]

    pl = config.padding_left
    pr = config.padding_right
    pt = config.padding_top
    pb = config.padding_bottom
    new_w = pl + w + pr
    new_h = pt + h + pb

    padded: list = []
    bg_solid = (*terminal_bg, 255)
    for frame in frames:
        fw, fh = frame.size
        px = frame.load()
        # Patch 4x4 corners: transparent/mixed pixels carry black backing from the
        # GIF palette; replace them with solid terminal_bg before compositing.
        c = 4
        for x0, y0 in [(0, 0), (fw - c, 0), (0, fh - c), (fw - c, fh - c)]:
            for y in range(y0, y0 + c):
                for x in range(x0, x0 + c):
                    if px[x, y] != bg_solid:
                        px[x, y] = bg_solid

        canvas = Image.new("RGBA", (new_w, new_h), bg_solid)
        canvas.paste(frame, (pl, pt))
        padded.append(canvas)

    return padded, terminal_bg


def _draw_gradient_circle(img, cx, cy, radius, base_color, highlight_color):
    base = _hex_rgba(base_color)
    highlight = _hex_rgba(highlight_color)

    # supersampling factor (anti-aliasing)
    scale = 4
    size = radius * 2 * scale

    highres = Image.new("RGBA", (size, size))
    px = highres.load()

    for y in range(size):
        for x in range(size):
            dx = (x + 0.5) / scale - radius
            dy = (y + 0.5) / scale - radius
            dist = math.sqrt(dx * dx + dy * dy)

            if dist <= radius:
                t = dist / radius
                r = int(highlight[0] * (1 - t) + base[0] * t)
                g = int(highlight[1] * (1 - t) + base[1] * t)
                b = int(highlight[2] * (1 - t) + base[2] * t)
                a = int(highlight[3] * (1 - t) + base[3] * t)
                px[x, y] = (r, g, b, a)
            else:
                px[x, y] = (0, 0, 0, 0)

    # downscale with high-quality filter
    circle = highres.resize((radius * 2, radius * 2), Image.LANCZOS)

    img.paste(circle, (cx - radius, cy - radius), circle)


def _build_chrome(
    layout: Layout,
    config: ThemeConfig,
    window_bg: tuple[int, int, int] = (30, 30, 30),
) -> tuple[Image.Image, Image.Image]:
    """Build the window chrome and a content-area mask.

    Returns:
        chrome: RGBA image — window bg, title bar, traffic lights, border. No transparent hole.
        mask:   L-mode image — 255 where content is visible, 0 elsewhere.
    """
    chrome = Image.new("RGBA", (layout.canvas_w, layout.canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(chrome)

    wx = int(layout.window_x)
    wy = int(layout.window_y)
    ww = layout.window_w
    wh = layout.window_h
    r = config.radius

    # Window background (rounded rect, no hole)
    draw.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=r, fill=(*window_bg, 255))

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
            try:
                title_font = ImageFont.truetype(str(_DM_SANS), size=12)
            except Exception:
                title_font = ImageFont.load_default()
            draw = ImageDraw.Draw(chrome)
            draw.text(
                (wx + ww // 2, title_cy),
                config.frame_bar_title,
                fill=_hex_rgba(_TITLE_COLOR),
                font=title_font,
                anchor="mm",
            )

    # Border
    if config.border_width > 0:
        draw = ImageDraw.Draw(chrome)
        draw.rounded_rectangle(
            [wx, wy, wx + ww, wy + wh],
            radius=r,
            outline=_hex_rgba(config.border_color),
            width=config.border_width,
        )

    # Content-area mask
    cx, cy = layout.content_x, layout.content_y
    cw, ch = layout.content_w, layout.content_h
    r_punch = min(r, cw // 2, ch // 2)

    mask = Image.new("L", chrome.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    # Round all 4 corners first
    mask_draw.rounded_rectangle([cx, cy, cx + cw - 1, cy + ch - 1], radius=r_punch, fill=255)
    # Square off the top corners when content is not flush with the window top
    if r_punch > 0 and cy > wy:
        mask_draw.rectangle([cx, cy, cx + cw - 1, cy + r_punch], fill=255)

    return chrome, mask


def _apply_watermark(base: Image.Image, config: ThemeConfig, margin_bottom: int = 0) -> Image.Image:
    if config.watermark is None:
        return base

    result = base.copy()
    draw = ImageDraw.Draw(result)

    font_size = (
        config.watermark_size
        if config.watermark_size is not None
        else int(max(20, min(30, base.width * 0.11)))
    )

    try:
        font = ImageFont.truetype(str(_DM_SANS), size=font_size)
    except Exception:
        try:
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    x = base.width // 2
    y = (
        base.height - margin_bottom // 2
        if margin_bottom > 0
        else base.height - 22 - font_size // 2
    )
    draw.text(
        (x, y),
        config.watermark,
        fill=_hex_rgba(config.watermark_color),
        font=font,
        anchor="mm",
    )
    return result


def _apply_scriptcast_watermark(base: Image.Image, config: ThemeConfig) -> Image.Image:
    if not config.scriptcast_watermark:
        return base

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


def apply_scriptcast_watermark(gif_path: Path, config: ThemeConfig) -> None:
    """Overlay the ScriptCast brand watermark on an existing GIF in-place (no frame path).

    Used when --frame is not set but scriptcast_watermark is True.
    """
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


def _chrome_colors(
    config: ThemeConfig, window_bg: tuple[int, int, int] = (30, 30, 30),
) -> list[tuple[int, int, int]]:
    """RGB colors that must be reserved in the GIF palette."""
    colors = [_hex_rgba(base)[:3] for _, base, _ in _TRAFFIC_LIGHTS]
    colors.append(window_bg)
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
    template_rgb: Image.Image,
    rgb_canvases: list[Image.Image],
    config: ThemeConfig,
    window_bg: tuple[int, int, int] = (30, 30, 30),
    max_samples: int = 20,
) -> Image.Image:
    chrome_colors = _chrome_colors(config, window_bg)
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


def apply_export(
    gif_path: Path,
    config: ThemeConfig,
    format: str = "gif",
    on_frame: Callable[[int, int], None] | None = None,
) -> None:
    """Post-process a GIF in-place: apply background, shadow, chrome, and watermarks.

    format: "gif" writes .gif (quantized 256 colours); "png" writes .png (full RGBA).
    on_frame: optional callback called after each frame is processed with (current, total) where
              current is 1-based frame number and total is the total number of frames.
    """
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

    if not raw_frames:
        return

    # Pre-process: detect terminal bg, bake padding into frames, fix transparent corners
    frames, terminal_bg = _preprocess_frames(raw_frames, config)

    content_w, content_h = frames[0].size
    layout = build_layout(content_w, content_h, config)
    _, _, resolved_mb, _ = _resolve_margin_sides(config)
    bg_shadow = _build_bg_shadow(layout, config)
    chrome, content_mask = _build_chrome(layout, config, window_bg=terminal_bg)

    output_path = gif_path if format == "gif" else gif_path.with_suffix(".png")

    total_frames = len(frames)
    rgba_frames = []
    for i, frame in enumerate(frames):
        canvas = bg_shadow.copy()
        canvas = Image.alpha_composite(canvas, chrome)
        content_canvas = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        content_canvas.paste(frame, (layout.content_x, layout.content_y))
        canvas = Image.composite(content_canvas, canvas, content_mask)
        canvas = _apply_watermark(canvas, config, margin_bottom=resolved_mb)
        canvas = _apply_scriptcast_watermark(canvas, config)
        rgba_frames.append(canvas)
        if on_frame is not None:
            on_frame(i + 1, total_frames)

    if format == "png":
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
        palette_ref = _build_global_palette(
            template_rgb, rgb_canvases, config, window_bg=terminal_bg,
        )
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
    frame_config: ThemeConfig | None = None,
    format: str = "gif",
    on_frame: Callable[[int, int], None] | None = None,
) -> Path:
    """Convert a .cast file to GIF or PNG using agg, then apply frame if configured.

    Raises AggNotFoundError if agg is not installed.
    Install: https://github.com/asciinema/agg

    format: "gif" writes .gif; "png" writes .png (full RGBA). Default here is "gif"
    for API backward compatibility — the CLI defaults to "png".
    on_frame: optional callback called after each frame is processed with (current, total) where
              current is 1-based frame number and total is the total number of frames.
    """
    agg = shutil.which("agg")
    if agg is None:
        raise AggNotFoundError(
            "agg not found. Install from: https://github.com/asciinema/agg"
        )
    cast_path = Path(cast_path)

    tmp_fd, tmp_gif_str = tempfile.mkstemp(suffix=".gif")
    os.close(tmp_fd)
    tmp_gif_path = Path(tmp_gif_str)

    try:
        subprocess.run([agg, str(cast_path), str(tmp_gif_path)], check=True)

        if frame_config is not None:
            apply_export(tmp_gif_path, frame_config, format=format, on_frame=on_frame)
            if format == "gif":
                final_path = cast_path.with_suffix(".gif")
                shutil.move(str(tmp_gif_path), str(final_path))
                output_path = final_path
            else:  # png
                tmp_png_path = tmp_gif_path.with_suffix(".png")
                final_path = cast_path.with_suffix(".png")
                shutil.move(str(tmp_png_path), str(final_path))
                tmp_gif_path.unlink()  # consumed by apply_export
                output_path = final_path
        else:
            final_path = cast_path.with_suffix(".gif")
            shutil.move(str(tmp_gif_path), str(final_path))
            output_path = final_path
    finally:
        if tmp_gif_path.exists():
            tmp_gif_path.unlink()
        tmp_png = tmp_gif_path.with_suffix(".png")
        if tmp_png.exists():
            tmp_png.unlink()

    return output_path
