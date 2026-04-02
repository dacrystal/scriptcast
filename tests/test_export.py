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
    assert FrameConfig().frame_bar_color == "#252535"


def test_frame_config_frame_bar_buttons_default():
    from scriptcast.config import FrameConfig
    assert FrameConfig().frame_bar_buttons is True


def test_frame_config_shadow_offset_x_default():
    from scriptcast.config import FrameConfig
    assert FrameConfig().shadow_offset_x == 0


def test_frame_config_no_title_field():
    from scriptcast.config import FrameConfig
    assert not hasattr(FrameConfig(), "title")


# ------------------------------------------------------------------ Layout
def test_layout_basic_no_margin_no_border():
    from scriptcast.config import FrameConfig
    from scriptcast.export import build_layout
    config = FrameConfig(
        padding_left=14, padding_right=14, padding_top=14, padding_bottom=14,
        border_width=0,
        margin_top=None, margin_right=None, margin_bottom=None, margin_left=None,
        background=None,  # auto margin = 0
        frame_bar=True,
    )
    layout = build_layout(200, 100, config)
    assert layout.content_w == 200
    assert layout.content_h == 100
    assert layout.window_w == 200 + 14 + 14   # 228
    assert layout.window_h == 28 + 14 + 100 + 14  # 156
    assert layout.canvas_w == 228
    assert layout.canvas_h == 156
    assert layout.content_x == 14
    assert layout.content_y == 28 + 14   # 42
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
    assert layout.canvas_w == 82 + 228 + 82   # 392
    assert layout.canvas_h == 82 + 156 + 82   # 320


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
    # canvas = 0 + 5 + 228 + 5 + 0 = 238
    assert layout.canvas_w == 238
    assert layout.canvas_h == 166
    # content_x = window_x + padding_left = 5 + 14 = 19
    assert layout.content_x == 19
    assert layout.content_y == int(5 + 28 + 14)  # 47


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
    assert layout.window_h == 0 + 14 + 100 + 14   # 128
    assert layout.content_y == 14   # no title bar contribution


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


# ------------------------------------------------------------------ _split_rgba
def test_split_rgba_six_chars_returns_full_opacity():
    from scriptcast.export import _split_rgba
    color, opacity = _split_rgba("#ff5f57")
    assert color == "#ff5f57"
    assert opacity == 1.0


def test_split_rgba_eight_chars_extracts_opacity():
    from scriptcast.export import _split_rgba
    color, opacity = _split_rgba("#0000004d")
    assert color == "#000000"
    assert abs(opacity - 77 / 255.0) < 0.001


def test_split_rgba_fully_transparent():
    from scriptcast.export import _split_rgba
    color, opacity = _split_rgba("#ffffff00")
    assert color == "#ffffff"
    assert opacity == 0.0


def test_split_rgba_fully_opaque_8_char():
    from scriptcast.export import _split_rgba
    color, opacity = _split_rgba("#ffffffff")
    assert color == "#ffffff"
    assert opacity == 1.0


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


# ------------------------------------------------------------------ _build_chrome_pil
def test_chrome_pil_is_rgba_correct_size():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    result = _build_chrome_pil(layout, config)
    assert result.mode == "RGBA"
    assert result.size == (layout.canvas_w, layout.canvas_h)


def test_chrome_pil_content_area_is_transparent():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         frame_bar=True)
    layout = build_layout(100, 50, config)
    result = _build_chrome_pil(layout, config)
    # Center of content area must be fully transparent
    cx = layout.content_x + layout.content_w // 2
    cy = layout.content_y + layout.content_h // 2
    assert result.getpixel((cx, cy))[3] == 0


def test_chrome_pil_outside_window_is_transparent():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config = FrameConfig(background="#aabbcc", shadow=False, border_width=0,
                         margin_top=40, margin_left=40, margin_right=40, margin_bottom=40)
    layout = build_layout(100, 50, config)
    result = _build_chrome_pil(layout, config)
    # Corner pixel (outside window) must be transparent in chrome
    assert result.getpixel((0, 0))[3] == 0


def test_chrome_pil_window_bg_area_is_opaque():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0,
                         frame_bar=False, padding_left=20, padding_right=20,
                         padding_top=20, padding_bottom=20)
    layout = build_layout(100, 50, config)
    result = _build_chrome_pil(layout, config)
    # Left padding area (inside window, not content) must be opaque
    px = int(layout.window_x) + 5   # 5px into window, before content_x
    py = layout.content_y + layout.content_h // 2
    assert result.getpixel((px, py))[3] == 255


def test_chrome_pil_title_bar_absent_when_frame_bar_false():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config_on = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=True)
    config_off = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=False)
    layout_on = build_layout(100, 50, config_on)
    layout_off = build_layout(100, 50, config_off)
    result_on = _build_chrome_pil(layout_on, config_on)
    result_off = _build_chrome_pil(layout_off, config_off)
    # With frame_bar=False the canvas is shorter (no title bar height)
    assert result_off.size[1] < result_on.size[1]


def test_chrome_pil_no_traffic_lights_when_buttons_false():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome_pil, build_layout
    config_yes = FrameConfig(background=None, shadow=False, border_width=0,
                              frame_bar=True, frame_bar_buttons=True)
    config_no = FrameConfig(background=None, shadow=False, border_width=0,
                             frame_bar=True, frame_bar_buttons=False)
    layout = build_layout(200, 100, config_yes)
    result_yes = _build_chrome_pil(layout, config_yes)
    result_no = _build_chrome_pil(layout, config_no)
    # Traffic light area differs
    assert result_yes.tobytes() != result_no.tobytes()


# ------------------------------------------------------------------ _build_svg
def test_build_svg_is_string_with_svg_tag():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(background=None, shadow=False)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert isinstance(svg, str)
    assert svg.lstrip().startswith("<svg")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_build_svg_canvas_dimensions():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert f'width="{layout.canvas_w}"' in svg
    assert f'height="{layout.canvas_h}"' in svg


def test_build_svg_has_content_hole_mask():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert "content-hole" in svg
    assert "<mask" in svg


def test_build_svg_three_traffic_lights():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(frame_bar=True, frame_bar_buttons=True)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert svg.count("<circle") == 3
    assert svg.count("radialGradient") >= 3


def test_build_svg_no_traffic_lights_when_buttons_false():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(frame_bar=True, frame_bar_buttons=False)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert "<circle" not in svg


def test_build_svg_no_title_bar_when_frame_bar_false():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(frame_bar=False)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert "window-clip" not in svg


def test_build_svg_title_text_escaped():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(frame_bar=True, frame_bar_title="foo & <bar>")
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert "foo &amp; &lt;bar&gt;" in svg
    assert "foo & <bar>" not in svg


def test_build_svg_border_present_when_nonzero():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(border_width=2, border_color="#ff0000ff")
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert "stroke=" in svg
    assert "#ff0000" in svg


def test_build_svg_no_border_when_zero():
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_svg, build_layout
    config = FrameConfig(border_width=0)
    layout = build_layout(200, 100, config)
    svg = _build_svg(layout, config)
    assert 'stroke=' not in svg


# ------------------------------------------------------------------ _build_chrome (dispatcher)
def test_build_chrome_returns_rgba_image():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    result = _build_chrome(layout, config)
    assert result.mode == "RGBA"
    assert result.size == (layout.canvas_w, layout.canvas_h)


def test_build_chrome_content_area_transparent():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import _build_chrome, build_layout
    config = FrameConfig(background=None, shadow=False, border_width=0)
    layout = build_layout(100, 50, config)
    result = _build_chrome(layout, config)
    cx = layout.content_x + layout.content_w // 2
    cy = layout.content_y + layout.content_h // 2
    assert result.getpixel((cx, cy))[3] == 0


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


def test_apply_export_apng_produces_png(tmp_path):
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.export import apply_export
    gif = tmp_path / "out.gif"
    _make_tiny_gif(gif, 40, 20)
    config = FrameConfig(background=None, shadow=False, border_width=0, frame_bar=False,
                         scriptcast_watermark=False)
    apply_export(gif, config, format="apng")
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
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("shutil.which", return_value="/usr/bin/agg"):
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
    gif_file = tmp_path / "scene.gif"
    config = FrameConfig()

    def fake_run(*args, **kwargs):
        gif_file.write_bytes(b"GIF89a")
        return MagicMock(returncode=0)

    with patch("shutil.which", return_value="/usr/bin/agg"):
        with patch("subprocess.run", side_effect=fake_run):
            with patch("scriptcast.export.apply_export") as mock_apply:
                generate_export(cast_file, config)

    mock_apply.assert_called_once_with(gif_file, config, format="gif")


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


def test_export_command_frame_bar_title_forwarded(tmp_path):
    import json
    from unittest.mock import patch
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(
        json.dumps({"version": 1, "width": 80, "height": 24,
                    "directive-prefix": "SC"}) + "\n"
        + json.dumps([0.0, "directive", "set theme-frame macos"]) + "\n"
    )
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_export", return_value=fake_gif) as mock_exp:
            result = runner.invoke(
                cli,
                ["export", str(sc_file), "--output-dir", str(tmp_path),
                 "--frame-bar-title", "MyDemo"],
            )
    assert result.exit_code == 0, result.output
    frame_config = mock_exp.call_args[0][1]
    assert frame_config is not None
    assert frame_config.frame_bar_title == "MyDemo"


def test_export_command_no_frame_passes_none(tmp_path):
    from unittest.mock import patch
    from click.testing import CliRunner
    from scriptcast.__main__ import cli

    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(_sc_content())
    fake_cast = tmp_path / "demo.cast"
    fake_gif = tmp_path / "demo.gif"

    runner = CliRunner()
    with patch("scriptcast.__main__.generate_from_sc", return_value=[fake_cast]):
        with patch("scriptcast.__main__.generate_export", return_value=fake_gif) as mock_exp:
            with patch("scriptcast.export.apply_scriptcast_watermark"):
                result = runner.invoke(cli, ["export", str(sc_file),
                                             "--output-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert mock_exp.call_args[0][1] is None


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


def test_gif_alias_still_works(tmp_path):
    """'gif' subcommand still exists for backwards compatibility."""
    from click.testing import CliRunner
    from scriptcast.__main__ import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["gif", "--help"])
    assert result.exit_code == 0
