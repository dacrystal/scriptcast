# tests/test_svg_frame.py

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _svg(config=None, canvas_w=400, canvas_h=300, wx=60, wy=60, ww=280, wh=180):
    from scriptcast.config import FrameConfig
    from scriptcast.svg_frame import build_svg
    if config is None:
        config = FrameConfig()
    return build_svg(config, canvas_w, canvas_h, wx, wy, ww, wh)


# ------------------------------------------------------------------
# Content rect
# ------------------------------------------------------------------

def test_content_rect_x_includes_padding_left():
    from scriptcast.config import FrameConfig
    from scriptcast.svg_frame import build_svg
    config = FrameConfig(padding_left=15)
    _, (cx, cy, cw, ch) = build_svg(config, 400, 300, 60, 60, 280, 180)
    assert cx == 60 + 15


def test_content_rect_y_includes_title_bar_and_padding_top():
    from scriptcast.config import FrameConfig
    from scriptcast.svg_frame import TITLE_BAR_HEIGHT, build_svg
    config = FrameConfig(padding_top=12)
    _, (cx, cy, cw, ch) = build_svg(config, 400, 300, 60, 60, 280, 180)
    assert cy == 60 + TITLE_BAR_HEIGHT + 12


def test_content_rect_width_excludes_both_paddings():
    from scriptcast.config import FrameConfig
    from scriptcast.svg_frame import build_svg
    config = FrameConfig(padding_left=10, padding_right=14)
    _, (cx, cy, cw, ch) = build_svg(config, 400, 300, 60, 60, 280, 180)
    assert cw == 280 - 10 - 14


def test_content_rect_height_excludes_title_bar_and_padding():
    from scriptcast.config import FrameConfig
    from scriptcast.svg_frame import TITLE_BAR_HEIGHT, build_svg
    config = FrameConfig(padding_top=8, padding_bottom=6)
    _, (cx, cy, cw, ch) = build_svg(config, 400, 300, 60, 60, 280, 180)
    assert ch == 180 - TITLE_BAR_HEIGHT - 8 - 6


# ------------------------------------------------------------------
# SVG structure
# ------------------------------------------------------------------

def test_build_svg_returns_string_and_4tuple():
    svg, rect = _svg()
    assert isinstance(svg, str)
    assert len(rect) == 4


def test_svg_starts_with_svg_tag():
    svg, _ = _svg()
    assert svg.lstrip().startswith('<svg')


def test_svg_has_xmlns():
    svg, _ = _svg()
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_svg_canvas_dimensions_in_root():
    svg, _ = _svg(canvas_w=500, canvas_h=350)
    assert 'width="500"' in svg
    assert 'height="350"' in svg


def test_svg_has_window_rect_at_correct_position():
    svg, _ = _svg(wx=70, wy=80, ww=260, wh=160)
    # window rect must have x=70, y=80, width=260, height=160
    assert 'x="70"' in svg
    assert 'y="80"' in svg
    assert 'width="260"' in svg
    assert 'height="160"' in svg


def test_svg_has_three_traffic_light_circles():
    svg, _ = _svg()
    assert svg.count('<circle') == 3


def test_svg_traffic_lights_have_radial_gradient_fill():
    svg, _ = _svg()
    assert 'radialGradient' in svg
    # All 3 circles use gradient fills (url(#light-N))
    assert svg.count('url(#light-') == 3


def test_svg_has_window_clip_path():
    svg, _ = _svg()
    assert 'clipPath' in svg
    assert 'window-clip' in svg


def test_svg_title_bar_uses_clip_path():
    svg, _ = _svg()
    # title bar rect references window-clip
    assert 'window-clip' in svg


# ------------------------------------------------------------------
# Shadow
# ------------------------------------------------------------------

def test_svg_shadow_enabled_has_decomposed_filter():
    from scriptcast.config import FrameConfig
    config = FrameConfig(shadow=True)
    svg, _ = _svg(config)
    assert 'feGaussianBlur' in svg
    assert 'feMerge' in svg
    assert 'feDropShadow' not in svg
    assert 'url(#shadow)' in svg


def test_svg_shadow_disabled_no_filter_element():
    from scriptcast.config import FrameConfig
    config = FrameConfig(shadow=False)
    svg, _ = _svg(config)
    assert 'feGaussianBlur' not in svg
    assert 'url(#shadow)' not in svg
    assert 'feMerge' not in svg


def test_svg_shadow_offset_y_in_filter():
    from scriptcast.config import FrameConfig
    config = FrameConfig(shadow=True, shadow_offset_y=25)
    svg, _ = _svg(config)
    assert 'dy="25"' in svg


# ------------------------------------------------------------------
# Background
# ------------------------------------------------------------------

def test_svg_no_background_no_bg_rect():
    from scriptcast.config import FrameConfig
    config = FrameConfig(background=None)
    svg, _ = _svg(config, canvas_w=400, canvas_h=300)
    # Should not have a rect spanning full canvas
    assert 'width="400" height="300"' not in svg


def test_svg_solid_background_rect():
    from scriptcast.config import FrameConfig
    config = FrameConfig(background="#aa00ff")
    svg, _ = _svg(config, canvas_w=400, canvas_h=300)
    assert '#aa00ff' in svg
    assert 'width="400"' in svg
    assert 'height="300"' in svg


def test_svg_gradient_background_has_linear_gradient():
    from scriptcast.config import FrameConfig
    config = FrameConfig(background="#ff0000,#0000ff")
    svg, _ = _svg(config)
    assert 'linearGradient' in svg
    assert '#ff0000' in svg
    assert '#0000ff' in svg


# ------------------------------------------------------------------
# Title text
# ------------------------------------------------------------------

def test_svg_no_title_no_text_element():
    from scriptcast.config import FrameConfig
    config = FrameConfig(title="")
    svg, _ = _svg(config)
    assert '<text' not in svg


def test_svg_title_adds_text_element():
    from scriptcast.config import FrameConfig
    config = FrameConfig(title="My Demo")
    svg, _ = _svg(config)
    assert '<text' in svg
    assert 'My Demo' in svg


def test_svg_title_with_special_chars_is_escaped():
    from scriptcast.config import FrameConfig
    config = FrameConfig(title="foo & <bar>")
    svg, _ = _svg(config)
    assert 'foo &amp; &lt;bar&gt;' in svg
    assert 'foo & <bar>' not in svg


# ------------------------------------------------------------------
# TITLE_BAR_HEIGHT consistency
# ------------------------------------------------------------------

def test_title_bar_height_matches_frame_module():
    from scriptcast.frame import TITLE_BAR_HEIGHT as frame_tbh
    from scriptcast.svg_frame import TITLE_BAR_HEIGHT as svg_tbh
    assert frame_tbh == svg_tbh
