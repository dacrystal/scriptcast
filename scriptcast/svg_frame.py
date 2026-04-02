# scriptcast/svg_frame.py
from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FrameConfig

# Must match TITLE_BAR_HEIGHT in frame.py
TITLE_BAR_HEIGHT = 28

_LIGHT_RADIUS = 6
_WINDOW_BG = "#1E1E1E"
_TITLEBAR_BG = "#252535"
_TITLE_COLOR = "#8A8A8A"

# (x_offset, base_color, highlight_color) — radial gradient gives 3D sphere look
_TRAFFIC_LIGHTS = [
    (12, "#FF5F57", "#FF8C80"),
    (32, "#FEBC2E", "#FFD466"),
    (52, "#28C840", "#5DE87F"),
]


def _split_rgba(hex_color: str) -> tuple[str, float]:
    """Return (#rrggbb, opacity_float) from a 6- or 8-char hex string."""
    h = hex_color.lstrip("#")
    if len(h) == 8:
        return f"#{h[:6]}", int(h[6:8], 16) / 255.0
    return f"#{h}", 1.0


def build_svg(
    config: FrameConfig,
    canvas_w: int,
    canvas_h: int,
    window_x: int,
    window_y: int,
    window_w: int,
    window_h: int,
) -> tuple[str, tuple[int, int, int, int]]:
    """Return (svg_string, (content_x, content_y, content_w, content_h)).

    The SVG defines all chrome — background, shadow, window rect, title bar,
    traffic lights, title text. No terminal content; PIL composites that later.
    Watermarks are intentionally omitted (applied by PIL after content paste).
    """
    content_x = window_x + config.padding_left
    content_y = window_y + TITLE_BAR_HEIGHT + config.padding_top
    content_w = window_w - config.padding_left - config.padding_right
    content_h = window_h - TITLE_BAR_HEIGHT - config.padding_top - config.padding_bottom
    title_cy = window_y + TITLE_BAR_HEIGHT // 2
    r = config.radius

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {canvas_w} {canvas_h}"'
        f' height="{canvas_h}" width="{canvas_w}">'
    )
    parts.append("<defs>")

    # Background gradient (only if 2-stop)
    if config.background is not None:
        stops = [p.strip() for p in config.background.split(",")]
        if len(stops) == 2:
            c1, a1 = _split_rgba(stops[0])
            c2, a2 = _split_rgba(stops[1])
            parts.append(
                f'<linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="0%">'
                f'<stop offset="0%" stop-color="{c1}" stop-opacity="{a1:.3f}"/>'
                f'<stop offset="100%" stop-color="{c2}" stop-opacity="{a2:.3f}"/>'
                f"</linearGradient>"
            )

    # Window clip path — used to give title bar rounded top corners
    parts.append(
        f'<clipPath id="window-clip">'
        f'<rect x="{window_x}" y="{window_y}"'
        f' width="{window_w}" height="{window_h}" rx="{r}" ry="{r}"/>'
        f"</clipPath>"
    )

    # Drop shadow filter
    if config.shadow:
        sc, sa = _split_rgba(config.shadow_color)
        std = config.shadow_radius / 2
        parts.append(
            f'<filter id="shadow" x="-60%" y="-60%" width="220%" height="220%">'
            f'<feDropShadow dx="0" dy="{config.shadow_offset_y}"'
            f' stdDeviation="{std:.1f}"'
            f' flood-color="{sc}" flood-opacity="{sa:.3f}"/>'
            f"</filter>"
        )

    # Radial gradients for 3D traffic lights
    for i, (_xoff, base, highlight) in enumerate(_TRAFFIC_LIGHTS):
        parts.append(
            f'<radialGradient id="light-{i}" cx="35%" cy="30%" r="65%">'
            f'<stop offset="0%" stop-color="{highlight}"/>'
            f'<stop offset="100%" stop-color="{base}"/>'
            f"</radialGradient>"
        )

    parts.append("</defs>")

    # Background rect
    if config.background is not None:
        stops = [p.strip() for p in config.background.split(",")]
        if len(stops) == 1:
            bc, ba = _split_rgba(stops[0])
            parts.append(
                f'<rect width="{canvas_w}" height="{canvas_h}"'
                f' fill="{bc}" fill-opacity="{ba:.3f}"/>'
            )
        else:
            parts.append(
                f'<rect width="{canvas_w}" height="{canvas_h}" fill="url(#bg-grad)"/>'
            )

    # Window rect (with optional shadow and border)
    shadow_attr = ' filter="url(#shadow)"' if config.shadow else ""
    border_attr = ""
    if config.border_width > 0:
        brc, bra = _split_rgba(config.border_color)
        border_attr = (
            f' stroke="{brc}" stroke-opacity="{bra:.3f}"'
            f' stroke-width="{config.border_width}"'
        )
    parts.append(
        f'<rect x="{window_x}" y="{window_y}"'
        f' width="{window_w}" height="{window_h}"'
        f' rx="{r}" ry="{r}" fill="{_WINDOW_BG}"{shadow_attr}{border_attr}/>'
    )

    # Title bar — clipped to window shape for rounded top corners
    parts.append(
        f'<rect x="{window_x}" y="{window_y}"'
        f' width="{window_w}" height="{TITLE_BAR_HEIGHT}"'
        f' fill="{_TITLEBAR_BG}" clip-path="url(#window-clip)"/>'
    )

    # Traffic lights
    for i, (x_off, _base, _hl) in enumerate(_TRAFFIC_LIGHTS):
        cx = window_x + x_off
        parts.append(
            f'<circle cx="{cx}" cy="{title_cy}" r="{_LIGHT_RADIUS}"'
            f' fill="url(#light-{i})"/>'
        )

    # Title text (centered in title bar)
    if config.title:
        tx = window_x + window_w // 2
        parts.append(
            f'<text x="{tx}" y="{title_cy}"'
            f' fill="{_TITLE_COLOR}"'
            f' font-family="system-ui,-apple-system,BlinkMacSystemFont,sans-serif"'
            f' font-size="12" text-anchor="middle" dominant-baseline="middle">'
            f"{html.escape(config.title)}</text>"
        )

    parts.append("</svg>")
    return "\n".join(parts), (content_x, content_y, content_w, content_h)
