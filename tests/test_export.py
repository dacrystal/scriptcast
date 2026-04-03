# tests/test_export.py

import pytest

# ------------------------------------------------------------------ FrameConfig
def test_frame_config_has_frame_bar():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame_bar is True


def test_frame_config_has_frame_bar_title():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame_bar_title == ""


def test_frame_config_frame_bar_color_default():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame_bar_color == "252535"


def test_frame_config_frame_bar_buttons_default():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame_bar_buttons is True


def test_frame_config_shadow_offset_x_default():
    from scriptcast.config import FrameConfig
    assert FrameConfig().shadow_offset_x == 0


def test_frame_config_no_title_field():
    from scriptcast.config import FrameConfig
    assert not hasattr(FrameConfig(), "title")


def test_frame_config_default_background_is_aurora():
    from scriptcast.config import FrameConfig
    assert FrameConfig().background == "1e1b4b,0d3b66"


def test_frame_config_default_frame_is_true():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame is True


def test_frame_config_default_colors_have_no_hash():
    from scriptcast.config import FrameConfig
    cfg = FrameConfig()
    assert not cfg.border_color.startswith("#")
    assert not cfg.frame_bar_color.startswith("#")
    assert not cfg.shadow_color.startswith("#")
    assert not cfg.watermark_color.startswith("#")


# ------------------------------------------------------------------ Layout
def test_layout_basic_no_margin_no_border():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        border_width=0,
        margin_top=None, margin_right=None, margin_bottom=None, margin_left=None,
        background=None,
        frame_bar=True,
    )
    layout = build_layout(200, 100, config)
    assert layout.content_w == 200
    assert layout.content_h == 100
    assert layout.window_w == 200          # no padding expansion
    assert layout.window_h == 28 + 100    # title bar + content only
    assert layout.canvas_w == 200
    assert layout.canvas_h == 128
    assert layout.content_x == 0          # no padding offset
    assert layout.content_y == 28         # title bar only
    assert layout.title_bar_h == 28


def test_layout_with_margin():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        border_width=0,
        margin_top=82, margin_right=82, margin_bottom=82, margin_left=82,
        background="#ff0000",
        frame_bar=True,
    )
    layout = build_layout(200, 100, config)
    assert layout.window_x == 82
    assert layout.window_y == 82
    assert layout.canvas_w == 82 + 200 + 82   # 364
    assert layout.canvas_h == 82 + 128 + 82   # 292


def test_layout_border_shifts_window_and_canvas():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        border_width=10,
        margin_top=None, margin_right=None, margin_bottom=None, margin_left=None,
        background=None,
        frame_bar=True,
    )
    layout = build_layout(200, 100, config)
    assert layout.half_bw == 5.0
    assert layout.window_x == 5.0
    assert layout.window_y == 5.0
    # canvas = 5 + 220 + 5 = 230 (border expands window_w from 200 to 220)
    assert layout.canvas_w == 230
    assert layout.canvas_h == 148   # 5 + 138 + 5 (border expands window_h from 128 to 138)
    # content_x = window_x + left_padding = 5 + 10 = 15
    assert layout.content_x == 15
    assert layout.content_y == int(5 + 28)   # 33


def test_layout_frame_bar_false_removes_title_bar_height():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        border_width=0,
        margin_top=None, margin_right=None, margin_bottom=None, margin_left=None,
        background=None,
        frame_bar=False,
    )
    layout = build_layout(200, 100, config)
    assert layout.title_bar_h == 0
    assert layout.window_h == 100    # content only, no title bar, no padding
    assert layout.content_y == 0    # no title bar contribution


def test_layout_border_zero_is_simple():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=0, padding_right=0, padding_top=0, padding_bottom=0,
        border_width=0,
        margin_top=None, margin_right=None, margin_bottom=None, margin_left=None,
        background=None,
        frame_bar=False,
    )
    layout = build_layout(80, 40, config)
    assert layout.window_x == 0
    assert layout.canvas_w == 80
    assert layout.canvas_h == 40
    assert layout.content_x == 0
    assert layout.content_y == 0


# ------------------------------------------------------------------ _hex_rgba
def test_hex_rgba_six_chars():
    from scriptcast.export import _hex_rgba
    assert _hex_rgba("#ff5f57") == (255, 95, 87, 255)


def test_hex_rgba_eight_chars():
    from scriptcast.export import _hex_rgba
    assert _hex_rgba("#0000004d") == (0, 0, 0, 77)


def test_hex_rgba_uppercase():
    from scriptcast.export import _hex_rgba
    assert _hex_rgba("#FF0000") == (255, 0, 0, 255)


def test_hex_rgba_invalid_length_raises():
    import pytest
    from scriptcast.export import _hex_rgba
    with pytest.raises(ValueError, match="_hex_rgba"):
        _hex_rgba("#fff")


# ------------------------------------------------------------------ _resolve_margin_sides
def test_resolve_margin_sides_no_background():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _resolve_margin_sides
    assert _resolve_margin_sides(FrameConfig(background=None)) == (0, 0, 0, 0)


def test_resolve_margin_sides_with_background_auto():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _resolve_margin_sides
    assert _resolve_margin_sides(FrameConfig(background="#ff0000")) == (82, 82, 82, 82)


def test_resolve_margin_sides_explicit_override():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _resolve_margin_sides
    config = FrameConfig(
        background="#ff0000",
        margin_top=10, margin_right=20, margin_bottom=30, margin_left=20,
    )
    assert _resolve_margin_sides(config) == (10, 20, 30, 20)


def test_resolve_margin_sides_partial_override():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _resolve_margin_sides
    config = FrameConfig(background="#ff0000", margin_bottom=120)
    t, r, b, l = _resolve_margin_sides(config)
    assert t == 82 and r == 82 and b == 120 and l == 82


# ------------------------------------------------------------------ removal guards
def test_split_rgba_removed():
    with pytest.raises(ImportError):
        from scriptcast.export import _split_rgba


def test_build_svg_removed():
    with pytest.raises(ImportError):
        from scriptcast.export import _build_svg


# ------------------------------------------------------------------ _build_bg_shadow
def test_bg_shadow_none_background_transparent():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background=None, shadow=False)
    layout = build_layout(100, 50, config)
    result = _build_bg_shadow(layout, config)
    assert result.size == (layout.canvas_w, layout.canvas_h)
    assert result.mode == "RGBA"
    assert result.getpixel((layout.canvas_w // 2, layout.canvas_h // 2)) == (0, 0, 0, 0)


def test_bg_shadow_solid_color():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background="#ff0000", shadow=False)
    layout = build_layout(100, 50, config)
    result = _build_bg_shadow(layout, config)
    r, g, b, a = result.getpixel((layout.canvas_w // 2, layout.canvas_h // 2))
    assert r == 255 and g == 0 and b == 0 and a == 255


def test_bg_shadow_gradient_left_color1():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background="#ff0000,#0000ff", shadow=False)
    layout = build_layout(100, 50, config)
    result = _build_bg_shadow(layout, config)
    r, g, b, a = result.getpixel((0, layout.canvas_h // 2))
    assert r == 255 and b == 0


def test_bg_shadow_gradient_right_color2():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background="#ff0000,#0000ff", shadow=False)
    layout = build_layout(100, 50, config)
    result = _build_bg_shadow(layout, config)
    r, g, b, a = result.getpixel((layout.canvas_w - 1, layout.canvas_h // 2))
    assert b == 255 and r == 0


def test_bg_shadow_gradient_too_many_stops_raises():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background="#ff0000,#00ff00,#0000ff", shadow=False)
    layout = build_layout(100, 50, config)
    with pytest.raises(ValueError, match="2 color stops"):
        _build_bg_shadow(layout, config)


def test_bg_shadow_adds_alpha_near_window():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(
        background="#ffffff",
        shadow=True, shadow_radius=5, shadow_offset_y=10, shadow_offset_x=0,
        shadow_color="#000000ff", radius=0,
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        margin_top=40, margin_right=40, margin_bottom=40, margin_left=40,
        border_width=0,
    )
    layout = build_layout(100, 50, config)
    plain = Image.new("RGBA", (layout.canvas_w, layout.canvas_h), (255, 255, 255, 255))
    result = _build_bg_shadow(layout, config)
    assert result.tobytes() != plain.tobytes()


def test_bg_shadow_disabled_no_change():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_bg_shadow, build_layout
    config = FrameConfig(background="#aabbcc", shadow=False)
    layout = build_layout(100, 50, config)
    r1 = _build_bg_shadow(layout, config)
    r2 = _build_bg_shadow(layout, config)
    assert r1.tobytes() == r2.tobytes()


# ------------------------------------------------------------------ _preprocess_frames
def test_preprocess_frames_padded_size():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _preprocess_frames
    frame = Image.new("RGBA", (100, 50), (40, 42, 54, 255))
    config = FrameConfig(padding_left=10, padding_right=10, padding_top=5, padding_bottom=5)
    padded, bg = _preprocess_frames([frame], config)
    assert padded[0].size == (120, 60)   # 10+100+10 wide, 5+50+5 tall


def test_preprocess_frames_detects_bg_from_top_center():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _preprocess_frames
    frame = Image.new("RGBA", (100, 50), (0, 0, 0, 255))
    frame.putpixel((50, 1), (40, 42, 54, 255))   # distinctive colour at sample point
    config = FrameConfig(padding_left=0, padding_right=0, padding_top=0, padding_bottom=0)
    _, bg = _preprocess_frames([frame], config)
    assert bg == (40, 42, 54)


def test_preprocess_frames_transparent_corners_show_bg():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _preprocess_frames
    w, h = 50, 30
    frame = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    frame.putpixel((0, 0), (0, 0, 0, 0))          # transparent top-left (like agg)
    bg_color = (40, 42, 54)
    frame.putpixel((w // 2, 1), (*bg_color, 255))  # set the bg-sample pixel
    config = FrameConfig(padding_left=5, padding_right=5, padding_top=5, padding_bottom=5)
    padded_frames, _ = _preprocess_frames([frame], config)
    padded = padded_frames[0]
    # (pad_left + 0, pad_top + 0) = (5, 5) — transparent corner must not overwrite bg
    assert padded.getpixel((5, 5))[:3] == bg_color


def test_preprocess_frames_padding_filled_with_bg():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _preprocess_frames
    w, h = 50, 30
    frame = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    bg_color = (40, 42, 54)
    frame.putpixel((w // 2, 1), (*bg_color, 255))
    config = FrameConfig(padding_left=10, padding_right=10, padding_top=10, padding_bottom=10)
    padded_frames, _ = _preprocess_frames([frame], config)
    padded = padded_frames[0]
    assert padded.getpixel((0, 0))[:3] == bg_color   # outer corner is padding bg
    assert padded.getpixel((5, 5))[:3] == bg_color   # still in padding region


# ------------------------------------------------------------------ _build_chrome
def test_chrome_returns_tuple():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    result = _build_chrome(layout, config)
    assert isinstance(result, tuple) and len(result) == 2


def test_chrome_image_is_rgba_correct_size():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    assert chrome.mode == "RGBA"
    assert chrome.size == (layout.canvas_w, layout.canvas_h)


def test_chrome_mask_is_L_mode_correct_size():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    assert mask.mode == "L"
    assert mask.size == (layout.canvas_w, layout.canvas_h)


def test_chrome_content_area_has_window_bg_color():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=True)
    layout = build_layout(100, 50, config)
    window_bg = (20, 20, 40)   # arbitrary test colour
    chrome, mask = _build_chrome(layout, config, window_bg=window_bg)
    cx = layout.content_x + layout.content_w // 2
    cy = layout.content_y + layout.content_h // 2
    assert chrome.getpixel((cx, cy))[:3] == window_bg


def test_chrome_outside_window_is_transparent():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         margin_top=40, margin_left=40, margin_right=40, margin_bottom=40)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    assert chrome.getpixel((0, 0))[3] == 0


def test_chrome_window_bg_area_is_opaque():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         frame_bar=False, padding_left=20, padding_right=20,
                         padding_top=20, padding_bottom=20)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    px = int(layout.window_x) + 5
    py = layout.content_y + layout.content_h // 2
    assert chrome.getpixel((px, py))[3] == 255


def test_chrome_mask_content_center_is_255():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    cx = layout.content_x + layout.content_w // 2
    cy = layout.content_y + layout.content_h // 2
    assert mask.getpixel((cx, cy)) == 255


def test_chrome_mask_outside_content_is_0():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         margin_top=40, margin_left=40, margin_right=40, margin_bottom=40)
    layout = build_layout(100, 50, config)
    chrome, mask = _build_chrome(layout, config)
    # Top-left corner of canvas is well outside the content area
    assert mask.getpixel((0, 0)) == 0


def test_chrome_mask_top_corners_square_with_title_bar():
    """When there is a title bar the top corners of the content area must be square."""
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         frame_bar=True, radius=10)
    layout = build_layout(200, 100, config)
    chrome, mask = _build_chrome(layout, config)
    # Top-left pixel of the content rect should be in the mask (255), not rounded away
    assert mask.getpixel((layout.content_x, layout.content_y)) == 255
    # Top-right
    assert mask.getpixel((layout.content_x + layout.content_w - 1, layout.content_y)) == 255


def test_chrome_mask_top_corners_rounded_without_title_bar_and_no_padding():
    """When content is flush with window top (no title bar, no top padding) top corners round."""
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         frame_bar=False, padding_top=0, padding_left=0,
                         padding_right=0, padding_bottom=0, radius=10)
    layout = build_layout(200, 100, config)
    # content_y == window_y when no title bar and no top padding
    assert layout.content_y == int(layout.window_y)
    chrome, mask = _build_chrome(layout, config)
    # The very top-left pixel should be rounded away (0), not square
    assert mask.getpixel((layout.content_x, layout.content_y)) == 0


def test_chrome_title_bar_absent_when_frame_bar_false():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config_on = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=True)
    config_off = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=False)
    layout_on = build_layout(100, 50, config_on)
    layout_off = build_layout(100, 50, config_off)
    chrome_on, _ = _build_chrome(layout_on, config_on)
    chrome_off, _ = _build_chrome(layout_off, config_off)
    assert chrome_off.size[1] < chrome_on.size[1]


def test_chrome_no_traffic_lights_when_buttons_false():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config_yes = FrameConfig(background=None, shadow=False, border_width=0,
                              frame_bar=True, frame_bar_buttons=True)
    config_no = FrameConfig(background=None, shadow=False, border_width=0,
                             frame_bar=True, frame_bar_buttons=False)
    layout = build_layout(200, 100, config_yes)
    chrome_yes, _ = _build_chrome(layout, config_yes)
    chrome_no, _ = _build_chrome(layout, config_no)
    assert chrome_yes.tobytes() != chrome_no.tobytes()


# ------------------------------------------------------------------ Watermarks
def test_watermark_none_returns_unchanged():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _apply_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_watermark(base, FrameConfig(watermark=None))
    assert result.tobytes() == base.tobytes()


def test_watermark_text_modifies_image():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _apply_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_watermark(base, FrameConfig(watermark="hello", watermark_size=14))
    assert result.tobytes() != base.tobytes()


def test_scriptcast_watermark_disabled_returns_unchanged():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _apply_scriptcast_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_scriptcast_watermark(base, FrameConfig(scriptcast_watermark=False))
    assert result.tobytes() == base.tobytes()


def test_scriptcast_watermark_enabled_modifies_image():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _apply_scriptcast_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_scriptcast_watermark(base, FrameConfig(scriptcast_watermark=True))
    assert result.tobytes() != base.tobytes()


# ------------------------------------------------------------------ apply_export
def _make_tiny_gif(path, width=40, height=20):
    """Create a minimal 2-frame RGBA GIF for testing."""
    from PIL import Image
    f1 = Image.new("RGB", (width, height), (30, 30, 30))
    f2 = Image.new("RGB", (width, height), (40, 40, 40))
    f1.quantize(colors=256).save(
        path, save_all=True, append_images=[f2.quantize(colors=256)],
        duration=100, loop=0,
    )


def test_apply_export_gif_produces_gif(tmp_path):
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import apply_export
    gif = tmp_path / "out.gif"
    _make_tiny_gif(gif, 40, 20)
    config = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=False,
                         scriptcast_watermark=False)
    apply_export(gif, config, format="gif")
    assert gif.exists()
    from PIL import Image
    img = Image.open(gif)
    assert img.format in ("GIF",)


def test_apply_export_png_produces_png_file(tmp_path):
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import apply_export
    gif = tmp_path / "out.gif"
    _make_tiny_gif(gif, 40, 20)
    config = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=False,
                         scriptcast_watermark=False)
    apply_export(gif, config, format="png")
    png = tmp_path / "out.png"
    assert png.exists()


def test_apply_export_with_frame_expands_canvas(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import apply_export
    gif = tmp_path / "out.gif"
    _make_tiny_gif(gif, 40, 20)
    config = FrameConfig(
        background=None, shadow=False, border_width=0,
        padding_left=10, padding_right=10, padding_top=10, padding_bottom=10,
        frame_bar=True, scriptcast_watermark=False,
    )
    apply_export(gif, config, format="gif")
    result = Image.open(gif)
    # Canvas must be larger than original content (40x20)
    assert result.size[0] > 40
    assert result.size[1] > 20


def test_apply_export_raises_without_pillow(tmp_path, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "PIL", None)
    from scriptcast.config import FrameConfig
    import importlib
    import scriptcast.export as exp_mod
    import builtins
    real_import = builtins.__import__
    def mock_import(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError("no PIL")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", mock_import)
    import pytest
    gif = tmp_path / "out.gif"
    gif.write_bytes(b"GIF89a")
    config = FrameConfig()
    with pytest.raises(RuntimeError, match="Pillow"):
        exp_mod.apply_export(gif, config)


# ------------------------------------------------------------------ generate_export
def test_generate_export_calls_agg(tmp_path):
    from unittest.mock import MagicMock, patch
    from scriptcast.export import generate_export
    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')
    with patch("scriptcast.export.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("scriptcast.export.shutil.which", return_value="/usr/bin/agg"):
            result = generate_export(cast_file)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "agg" in args[0]
    assert str(cast_file) in args
    assert result == tmp_path / "scene.gif"


def test_generate_export_missing_agg_raises():
    import pytest
    from unittest.mock import patch
    from pathlib import Path
    from scriptcast.export import AggNotFoundError, generate_export
    with patch("shutil.which", return_value=None):
        with pytest.raises(AggNotFoundError, match="agg"):
            generate_export(Path("scene.cast"))


def test_generate_export_calls_apply_export_when_config_provided(tmp_path):
    from unittest.mock import MagicMock, patch
    from scriptcast.config import FrameConfig
    from scriptcast.export import generate_export
    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')
    config = FrameConfig()

    def fake_run(*args, **kwargs):
        # Write to the temp gif path that agg would write to (second arg)
        import os
        from PIL import Image
        temp_path = args[0][2]  # The temp gif path is the third argument to agg
        frame = Image.new("RGB", (80, 24), (30, 30, 30))
        frame.save(temp_path, format="GIF")
        return MagicMock(returncode=0)

    with patch("scriptcast.export.shutil.which", return_value="/usr/bin/agg"):
        with patch("scriptcast.export.subprocess.run", side_effect=fake_run):
            with patch("scriptcast.export.apply_export") as mock_apply:
                result = generate_export(cast_file, config)

    # apply_export should be called once with config and format
    mock_apply.assert_called_once()
    call_args = mock_apply.call_args
    assert call_args[0][1] == config
    assert call_args[1]["format"] == "gif"
    # Result should be the final gif path in the cast directory
    assert result == tmp_path / "scene.gif"


def test_generate_export_skips_apply_export_when_no_config(tmp_path):
    from unittest.mock import MagicMock, patch
    from scriptcast.export import generate_export
    cast_file = tmp_path / "scene.cast"
    cast_file.write_text('{"version":2}\n')

    with patch("shutil.which", return_value="/usr/bin/agg"):
        with patch("subprocess.run"):
            with patch("scriptcast.export.apply_export") as mock_apply:
                try:
                    generate_export(cast_file)
                except Exception:
                    pass

    mock_apply.assert_not_called()


def test_generate_export_png_format_no_temp_files_in_cast_dir(tmp_path):
    """format='png': final .png is in cast dir, no temp gifs or pngs left behind."""
    from unittest.mock import patch, MagicMock
    from scriptcast.export import generate_export, apply_export
    from scriptcast.config import FrameConfig

    cast_path = tmp_path / "demo.cast"
    cast_path.write_text('{"version":2,"width":80,"height":24}\n')

    def fake_agg(cmd, **kwargs):
        from PIL import Image
        frame = Image.new("RGB", (80, 24), (30, 30, 30))
        frame.save(str(cmd[2]), format="GIF")

    def fake_apply_export(gif_path, config, format):
        # Simulate what apply_export does: write .png next to the gif
        from PIL import Image
        frame = Image.new("RGBA", (80, 24), (30, 30, 30, 255))
        out = gif_path.with_suffix(".png")
        frame.save(str(out), format="PNG")

    config = FrameConfig(frame=True, scriptcast_watermark=False, shadow=False, background=None)
    with patch("scriptcast.export.subprocess.run", side_effect=fake_agg), \
         patch("scriptcast.export.shutil.which", return_value="/usr/bin/agg"), \
         patch("scriptcast.export.apply_export", side_effect=fake_apply_export):
        result = generate_export(cast_path, frame_config=config, format="png")

    assert result == tmp_path / "demo.png"
    assert (tmp_path / "demo.png").exists()
    # No stray temp files in cast dir
    assert not list(tmp_path.glob("*.gif"))
    assert len(list(tmp_path.glob("*.png"))) == 1


# ------------------------------------------------------------------ CLI: export command
def _sc_content() -> str:
    import json
    return json.dumps({"version": 1, "width": 80, "height": 24,
                       "directive-prefix": "SC"}) + "\n"


def test_export_command_exists():
    from click.testing import CliRunner
    from scriptcast.__main__ import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0
    assert "export" in result.output.lower() or "agg" in result.output.lower()


def test_export_command_default_frame_passes_config(tmp_path):
    from unittest.mock import patch
    from click.testing import CliRunner
    from scriptcast.__main__ import cli
    from scriptcast.config import FrameConfig

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_export", return_value=fake_gif) as mock_exp:
            with patch("scriptcast.__main__.apply_scriptcast_watermark"):
                result = runner.invoke(cli, ["export", str(sc_file),
                                             "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert isinstance(mock_exp.call_args[0][1], FrameConfig)


def test_export_command_error_is_clean(tmp_path):
    from unittest.mock import patch
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch(
            "scriptcast.__main__.generate_export",
            side_effect=RuntimeError("Pillow not installed"),
        ):
            result = runner.invoke(cli, ["export", str(sc_file),
                                         "--output-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "Pillow not installed" in result.output


def test_apply_export_content_visible_in_content_area(tmp_path):
    """Content pixels must appear at the content position in the output."""
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import apply_export, build_layout

    # Create a GIF with a solid bright-red frame
    gif = tmp_path / "red.gif"
    f = Image.new("RGB", (80, 40), (255, 0, 0))
    f.quantize(colors=256).save(gif, save_all=True, duration=100, loop=0)

    config = FrameConfig(
        background=None, shadow=False, border_width=0,
        frame_bar=False, padding_left=0, padding_right=0,
        padding_top=0, padding_bottom=0,
        scriptcast_watermark=False,
    )
    apply_export(gif, config, format="png")
    png = tmp_path / "red.png"
    result = Image.open(png).convert("RGBA")

    layout = build_layout(80, 40, config)
    cx = layout.content_x + layout.content_w // 2
    cy = layout.content_y + layout.content_h // 2
    r, g, b, a = result.getpixel((cx, cy))
    # Content (red) must be visible at the content centre
    assert r > 200 and g < 50 and b < 50


def test_apply_watermark_centered_in_margin():
    """With margin_bottom set, watermark position differs from the no-margin default."""
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.export import _apply_watermark

    img = Image.new("RGBA", (400, 300), (30, 30, 30, 255))
    config = FrameConfig(watermark="test", watermark_size=20)

    result_with_margin = _apply_watermark(img, config, margin_bottom=82)
    result_no_margin = _apply_watermark(img, config, margin_bottom=0)

    assert result_with_margin.size == (400, 300)
    assert result_no_margin.size == (400, 300)
    # Different margin_bottom values must produce different watermark positions
    assert result_with_margin.tobytes() != result_no_margin.tobytes()


def test_apply_export_png_format_writes_png_file(tmp_path):
    """apply_export with format='png' writes a PNG file with RGBA (not quantized palette)."""
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.export import apply_export
    from scriptcast.config import FrameConfig

    # Create a minimal single-frame GIF
    frame = Image.new("RGBA", (80, 24), (30, 30, 30, 255))
    gif_path = tmp_path / "test.gif"
    frame.convert("RGB").save(str(gif_path), format="GIF")

    config = FrameConfig(frame=False, scriptcast_watermark=False, shadow=False, background=None)
    apply_export(gif_path, config, format="png")

    # Should write to test.png
    png_path = tmp_path / "test.png"
    assert png_path.exists(), "format='png' should write .png file"

    # The output should be RGBA PNG (not quantized palette mode P)
    output = Image.open(png_path)
    # format='png' must produce full RGBA, not a quantized palette mode
    assert output.mode == "RGBA", f"Expected RGBA PNG but got mode {output.mode}"


def test_generate_export_no_temp_gif_left_in_cast_dir(tmp_path):
    """Intermediate .gif from agg must not be left in the cast directory."""
    from unittest.mock import patch
    from scriptcast.export import generate_export

    cast_path = tmp_path / "demo.cast"
    cast_path.write_text('{"version":2,"width":80,"height":24}\n')

    def fake_agg(cmd, check):
        # Write a minimal gif to the path agg would write to (second arg)
        from PIL import Image
        frame = Image.new("RGB", (80, 24), (30, 30, 30))
        frame.save(str(cmd[2]), format="GIF")

    with patch("scriptcast.export.subprocess.run", side_effect=fake_agg), \
         patch("scriptcast.export.shutil.which", return_value="/usr/bin/agg"):
        generate_export(cast_path, frame_config=None, format="gif")

    # Only the final .gif should exist; no stray temp files in cast dir
    files_in_dir = list(tmp_path.glob("*.gif"))
    assert len(files_in_dir) == 1
    assert files_in_dir[0] == tmp_path / "demo.gif"


def test_generate_export_cleans_up_temp_gif_on_failure(tmp_path):
    """Temp gif is cleaned up even when agg succeeds but processing fails."""
    from unittest.mock import patch
    from scriptcast.export import generate_export
    from scriptcast.config import FrameConfig

    cast_path = tmp_path / "demo.cast"
    cast_path.write_text('{"version":2,"width":80,"height":24}\n')

    def fake_agg(cmd, check):
        from PIL import Image
        frame = Image.new("RGB", (80, 24), (30, 30, 30))
        frame.save(str(cmd[2]), format="GIF")

    config = FrameConfig(frame=True, scriptcast_watermark=False, shadow=False, background=None)

    with patch("scriptcast.export.subprocess.run", side_effect=fake_agg), \
         patch("scriptcast.export.shutil.which", return_value="/usr/bin/agg"), \
         patch("scriptcast.export.apply_export", side_effect=RuntimeError("boom")):
        try:
            generate_export(cast_path, frame_config=config, format="gif")
        except RuntimeError:
            pass

    # No temp gifs should be left in the cast directory
    assert not any(tmp_path.glob("*.gif"))
