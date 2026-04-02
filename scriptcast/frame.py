# scriptcast/frame.py
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig

try:
    from PIL.Image import Image as PILImage
except ImportError:  # Pillow not installed — only used at runtime inside functions
    PILImage = object  # type: ignore[assignment,misc]

# SVG rendering path (cairosvg). Falls back to PIL if cairosvg is absent.
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
_TITLEBAR_BG = "#252535"


def _hex_rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Parse a 6- or 8-character hex color string into an RGBA tuple."""
    h = hex_color.lstrip("#")
    if len(h) not in (6, 8):
        raise ValueError(f"_hex_rgba expects 6 or 8 hex digits, got {len(h)} in {hex_color!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


_CHROME_COLORS: list[tuple[int, int, int]] = (
    [_hex_rgba(base)[:3] for _, base, _ in _TRAFFIC_LIGHTS]
    + [_hex_rgba(_WINDOW_BG)[:3], _hex_rgba(_TITLEBAR_BG)[:3], _hex_rgba(_TITLE_COLOR)[:3]]
)


def _resolve_margin_sides(config: FrameConfig) -> tuple[int, int, int, int]:
    """Return (top, right, bottom, left), auto-defaulting None to 82 if background is set, else 0."""
    auto = 82 if config.background is not None else 0
    t = config.margin_top if config.margin_top is not None else auto
    r = config.margin_right if config.margin_right is not None else auto
    b = config.margin_bottom if config.margin_bottom is not None else auto
    l = config.margin_left if config.margin_left is not None else auto
    return (t, r, b, l)


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

    dest_x = window_x - pad
    dest_y = window_y - pad + offset_y
    shadow_canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_canvas.paste(shadow_img, (dest_x, dest_y))
    return Image.alpha_composite(base, shadow_canvas)


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
    return result


def _apply_window_border(
    base: PILImage,
    window_x: int,
    window_y: int,
    window_w: int,
    window_h: int,
    config: FrameConfig,
) -> PILImage:
    if config.border_width <= 0:
        return base

    from PIL import ImageDraw

    result = base.copy()
    draw = ImageDraw.Draw(result)
    box = [window_x, window_y, window_x + window_w, window_y + window_h]
    draw.rounded_rectangle(
        box,
        radius=config.radius,
        outline=_hex_rgba(config.border_color),
        width=config.border_width,
    )
    return result


def _make_content_mask(
    canvas_size: tuple[int, int],
    content_x: int,
    content_y: int,
    content_w: int,
    content_h: int,
    radius: int,
) -> PILImage:
    """Return an 'L' mask image the same size as the canvas.

    White (255) where terminal content should show; black (0) elsewhere.
    Bottom corners are rounded to match the window radius; top corners are
    straight (the title-bar separator is a flat edge, not a curve).
    """
    from PIL import Image, ImageDraw

    mask = Image.new("L", canvas_size, 0)
    draw = ImageDraw.Draw(mask)
    r = min(radius, content_w // 2, content_h // 2)
    box = [content_x, content_y, content_x + content_w - 1, content_y + content_h - 1]
    # Full rounded rect first (rounds all four corners)
    draw.rounded_rectangle(box, radius=r, fill=255)
    # Flatten the top corners by overdrawing a plain rect over the top r rows
    if r > 0:
        draw.rectangle(
            [content_x, content_y, content_x + content_w - 1, content_y + r],
            fill=255,
        )
    return mask


def _draw_gradient_circle(
    img: PILImage,
    cx: int,
    cy: int,
    radius: int,
    base_color: str,
    highlight_color: str,
) -> None:
    """Paint a radial-gradient circle onto img in-place, simulating a 3D sphere.

    Draws concentric filled circles stepping from highlight_color at the centre
    to base_color at the edge. The highlight is offset slightly toward the
    upper-left to simulate a directional light source.
    """
    from PIL import Image, ImageDraw

    steps = 8
    base = _hex_rgba(base_color)
    highlight = _hex_rgba(highlight_color)
    offset_x = int(radius * 0.20)

    for i in range(steps, 0, -1):
        t = i / steps  # 1.0 at outermost, 0.0 at innermost
        r = int(base[0] * t + highlight[0] * (1 - t))
        g = int(base[1] * t + highlight[1] * (1 - t))
        b = int(base[2] * t + highlight[2] * (1 - t))
        circle_r = int(radius * (i + 1) / (steps + 1))
        # Shift centre toward upper-left for innermost rings
        shift = int((1 - t) * offset_x)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.ellipse(
            [cx - circle_r - shift, cy - circle_r - shift,
             cx + circle_r - shift, cy + circle_r - shift],
            fill=(r, g, b, 255),
        )
        img.paste(layer, (0, 0), layer)


def _apply_title_bar(
    base: PILImage,
    window_x: int,
    window_y: int,
    window_w: int,
    window_h: int,
    config: FrameConfig,
) -> PILImage:
    from PIL import Image, ImageDraw

    result = base.copy()

    # --- Titlebar background clipped to window rounded corners ---
    r = config.radius
    # Build a clip mask: white only inside the window's rounded rect AND above content
    clip = Image.new("L", result.size, 0)
    clip_draw = ImageDraw.Draw(clip)
    clip_draw.rounded_rectangle(
        [window_x, window_y, window_x + window_w, window_y + window_h],
        radius=r, fill=255,
    )
    # Black out everything below the title bar
    clip_draw.rectangle(
        [window_x, window_y + TITLE_BAR_HEIGHT, window_x + window_w, window_y + window_h],
        fill=0,
    )
    titlebar_fill = Image.new("RGBA", result.size, _hex_rgba(_TITLEBAR_BG))
    result = Image.composite(titlebar_fill, result, clip)

    # --- Traffic lights and title text ---
    y_center = window_y + TITLE_BAR_HEIGHT // 2

    for light_x, base_color, highlight_color in _TRAFFIC_LIGHTS:
        cx = window_x + light_x
        _draw_gradient_circle(result, cx, y_center, _LIGHT_RADIUS, base_color, highlight_color)

    if config.title:
        draw = ImageDraw.Draw(result)
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
    """Overlay the scriptcast brand watermark on an existing GIF in-place.

    Used when --frame is not set. Canvas size is unchanged. Requires Pillow.
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

    out_frames = []
    for raw in raw_frames:
        with_wm = _apply_scriptcast_watermark(raw, config)
        out_frames.append(with_wm.convert("RGB").quantize(colors=256, dither=Dither.NONE))

    out_frames[0].save(
        gif_path,
        save_all=True,
        append_images=out_frames[1:],
        loop=0,
        duration=durations,
        optimize=False,
    )


def _build_global_palette(
    template_rgb: PILImage,
    rgb_canvases: list[PILImage],
    max_samples: int = 20,
) -> PILImage:
    """Build a shared P-mode palette image from the template + sampled content frames.

    Samples up to max_samples evenly-distributed frames so that the palette covers
    both static chrome colors and the range of terminal ANSI colors.
    """
    from PIL import Image

    n = len(rgb_canvases)
    if max_samples <= 1 or n <= max_samples:
        indices = list(range(n))
    else:
        indices = [int(round(i * (n - 1) / (max_samples - 1))) for i in range(max_samples)]

    sampled = [rgb_canvases[i] for i in indices]
    w, h = template_rgb.size
    # Stack template + sampled frames vertically for palette derivation
    composite = Image.new("RGB", (w, h * (1 + len(sampled))))
    composite.paste(template_rgb, (0, 0))
    for idx, frame in enumerate(sampled):
        composite.paste(frame, (0, h * (idx + 1)))
    n_chrome = len(_CHROME_COLORS)
    content_ref = composite.quantize(colors=256 - n_chrome)
    chrome_bytes = b"".join(bytes(c) for c in _CHROME_COLORS)
    raw_palette = content_ref.getpalette() or []
    content_bytes = bytes(raw_palette[: (256 - n_chrome) * 3])
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(chrome_bytes + content_bytes)
    return palette_img


def apply_frame(gif_path: Path, config: FrameConfig, format: str = "gif") -> None:
    """Post-process a GIF in-place: add background, shadow, window chrome, and optional watermark.

    When cairosvg is installed, uses SVG-based chrome rendering for superior quality.
    Falls back to PIL drawing when cairosvg is unavailable.

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

    mt, mr, mb, ml = _resolve_margin_sides(config)

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
    window_w = frame_w + config.padding_left + config.padding_right
    window_h = frame_h + config.padding_top + config.padding_bottom + TITLE_BAR_HEIGHT
    canvas_w = window_w + ml + mr
    canvas_h = window_h + mt + mb
    window_x = ml
    window_y = mt

    output_path = gif_path if format == "gif" else gif_path.with_suffix(".png")

    if _svg_available:
        from . import svg_frame as _svg_frame

        svg_str, (content_x, content_y, content_w, content_h) = _svg_frame.build_svg(
            config, canvas_w, canvas_h, window_x, window_y, window_w, window_h
        )
        png_bytes = _cairosvg.svg2png(bytestring=svg_str.encode())
        chrome = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        _full_mask = _make_content_mask(
            chrome.size, content_x, content_y, content_w, content_h, config.radius
        )
        # PIL paste() requires the mask to match the source image size, not the canvas.
        content_mask = _full_mask.crop(
            (content_x, content_y, content_x + content_w, content_y + content_h)
        )

        rgba_canvases: list[Image.Image] = []
        for raw in raw_frames:
            canvas = chrome.copy()
            canvas.paste(raw, (content_x, content_y), content_mask)
            canvas = _apply_watermark(canvas, config)
            canvas = _apply_scriptcast_watermark(canvas, config)
            rgba_canvases.append(canvas)

        if format == "apng":
            rgba_canvases[0].save(
                output_path,
                format="PNG",
                save_all=True,
                append_images=rgba_canvases[1:],
                loop=0,
                duration=durations,
            )
        else:
            rgb_canvases = [c.convert("RGB") for c in rgba_canvases]
            template_rgb = chrome.convert("RGB")
            palette_ref = _build_global_palette(template_rgb, rgb_canvases)
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
        return

    # ----------------------------------------------------------------
    # PIL fallback path (used when cairosvg is not installed)
    # ----------------------------------------------------------------
    bw = config.border_width
    content_x = window_x + config.padding_left + bw
    content_y = window_y + TITLE_BAR_HEIGHT + config.padding_top + bw
    # content_w/h stay at frame dimensions (not reduced by bw) — matches SVG path convention.
    # The border stroke drawn by _apply_window_border covers any incidental overlap on the
    # right/bottom edges. Valid when padding >= bw, which holds for typical usage.
    content_w = frame_w
    content_h = frame_h

    template = _build_background(canvas_w, canvas_h, config)
    template = _apply_shadow(template, window_x, window_y, window_w, window_h, config)
    template = _apply_window_rect(template, window_x, window_y, window_w, window_h, config)
    template = _apply_title_bar(template, window_x, window_y, window_w, window_h, config)
    template = _apply_window_border(template, window_x, window_y, window_w, window_h, config)

    _full_mask = _make_content_mask(
        template.size, content_x, content_y, content_w, content_h, config.radius
    )
    # PIL paste() requires the mask to match the source image size, not the canvas.
    content_mask = _full_mask.crop(
        (content_x, content_y, content_x + content_w, content_y + content_h)
    )

    rgba_canvases_pil = []
    for raw in raw_frames:
        canvas = template.copy()
        canvas.paste(raw, (content_x, content_y), content_mask)
        canvas = _apply_watermark(canvas, config)
        canvas = _apply_scriptcast_watermark(canvas, config)
        rgba_canvases_pil.append(canvas)

    if format == "apng":
        rgba_canvases_pil[0].save(
            output_path,
            format="PNG",
            save_all=True,
            append_images=rgba_canvases_pil[1:],
            loop=0,
            duration=durations,
        )
    else:
        template_rgb = template.convert("RGB")
        rgb_canvases = [c.convert("RGB") for c in rgba_canvases_pil]
        palette_ref = _build_global_palette(template_rgb, rgb_canvases)
        out_frames = [
            frame.quantize(palette=palette_ref, dither=Dither.NONE) for frame in rgb_canvases
        ]
        out_frames[0].save(
            output_path,
            save_all=True,
            append_images=out_frames[1:],
            loop=0,
            duration=durations,
            optimize=False,
        )
