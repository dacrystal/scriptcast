# tests/test_frame.py
import pytest


def _make_tiny_gif(path, width=40, height=20):
    """Create a minimal 2-frame GIF for testing."""
    from PIL import Image
    f1 = Image.new("RGB", (width, height), (30, 30, 30))
    f2 = Image.new("RGB", (width, height), (40, 40, 40))
    f1.quantize(colors=256).save(
        path, save_all=True, append_images=[f2.quantize(colors=256)], duration=100, loop=0
    )


def test_hex_rgba_six_chars():
    from scriptcast.frame import _hex_rgba
    assert _hex_rgba("#ff5f57") == (255, 95, 87, 255)


def test_hex_rgba_eight_chars():
    from scriptcast.frame import _hex_rgba
    assert _hex_rgba("#0000004d") == (0, 0, 0, 77)


def test_hex_rgba_uppercase():
    from scriptcast.frame import _hex_rgba
    assert _hex_rgba("#FF0000") == (255, 0, 0, 255)


def test_hex_rgba_invalid_length_raises():
    from scriptcast.frame import _hex_rgba
    with pytest.raises(ValueError, match="_hex_rgba"):
        _hex_rgba("#fff")


def test_resolve_margin_sides_no_background():
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _resolve_margin_sides
    assert _resolve_margin_sides(FrameConfig(background=None)) == (0, 0, 0, 0)


def test_resolve_margin_sides_with_background_auto():
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _resolve_margin_sides
    assert _resolve_margin_sides(FrameConfig(background="#ff0000")) == (82, 82, 82, 82)


def test_resolve_margin_sides_explicit_override():
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _resolve_margin_sides
    config = FrameConfig(background="#ff0000", margin_top=10, margin_right=20,
                         margin_bottom=30, margin_left=20)
    assert _resolve_margin_sides(config) == (10, 20, 30, 20)


def test_resolve_margin_sides_partial_override():
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _resolve_margin_sides
    # Only bottom overridden; others auto to 82 because background is set
    config = FrameConfig(background="#ff0000", margin_bottom=120)
    t, r, b, l = _resolve_margin_sides(config)
    assert t == 82 and r == 82 and b == 120 and l == 82


def test_resolve_margin_sides_explicit_zero():
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _resolve_margin_sides
    config = FrameConfig(background="#ff0000",
                         margin_top=0, margin_right=0, margin_bottom=0, margin_left=0)
    assert _resolve_margin_sides(config) == (0, 0, 0, 0)


def test_background_none_creates_transparent_canvas():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _build_background
    config = FrameConfig(background=None)
    result = _build_background(100, 50, config)
    assert result.size == (100, 50)
    assert result.mode == "RGBA"
    assert result.getpixel((50, 25)) == (0, 0, 0, 0)


def test_background_solid_fills_with_color():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _build_background
    config = FrameConfig(background="#ff0000")
    result = _build_background(100, 50, config)
    r, g, b, a = result.getpixel((50, 25))
    assert r == 255 and g == 0 and b == 0 and a == 255


def test_background_gradient_left_is_color1():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _build_background
    config = FrameConfig(background="#ff0000,#0000ff")
    result = _build_background(100, 50, config)
    r, g, b, a = result.getpixel((0, 25))
    assert r == 255 and b == 0


def test_background_gradient_right_is_color2():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _build_background
    config = FrameConfig(background="#ff0000,#0000ff")
    result = _build_background(100, 50, config)
    r, g, b, a = result.getpixel((99, 25))
    assert b == 255 and r == 0


def test_background_gradient_too_many_stops_raises():
    pytest.importorskip("PIL")
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _build_background
    config = FrameConfig(background="#ff0000,#00ff00,#0000ff")
    with pytest.raises(ValueError, match="2 color stops"):
        _build_background(100, 50, config)


def test_shadow_disabled_returns_unchanged():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_shadow
    config = FrameConfig(shadow=False)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    result = _apply_shadow(base, 50, 50, 100, 100, config)
    assert result.tobytes() == base.tobytes()


def test_shadow_adds_visible_pixels_near_window():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_shadow
    config = FrameConfig(shadow=True, shadow_radius=5, shadow_offset_y=10,
                         shadow_color="#000000ff", radius=0)
    base = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    result = _apply_shadow(base, 50, 50, 100, 100, config)
    # Just below window bottom + offset (50+100+10=160) should have non-zero alpha
    _, _, _, a = result.getpixel((100, 162))
    assert a > 0


def test_window_rect_fills_center():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_window_rect
    config = FrameConfig(border_width=0, radius=0)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    result = _apply_window_rect(base, 10, 10, 100, 80, config)
    _, _, _, a = result.getpixel((60, 50))
    assert a == 255


def test_window_rect_border_color_applied():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_window_rect
    config = FrameConfig(border_color="#ff0000ff", border_width=3, radius=0)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    result = _apply_window_rect(base, 10, 10, 100, 80, config)
    r, g, b, a = result.getpixel((60, 10))
    assert r == 255 and g == 0 and b == 0


def test_title_bar_red_traffic_light():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import TITLE_BAR_HEIGHT, _apply_title_bar
    config = FrameConfig()
    base = Image.new("RGBA", (200, 200), (30, 30, 30, 255))
    result = _apply_title_bar(base, 0, 0, 200, 200, config)
    r, g, b, a = result.getpixel((12, TITLE_BAR_HEIGHT // 2))
    # Centre pixel is the highlight colour #FF8C80 — still clearly red
    assert r > 200 and g > 100 and b > 100 and r > g


def test_title_bar_with_title_differs_from_without():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_title_bar
    base = Image.new("RGBA", (200, 200), (30, 30, 30, 255))
    no_title = _apply_title_bar(base, 0, 0, 200, 200, FrameConfig(title=""))
    with_title = _apply_title_bar(base, 0, 0, 200, 200, FrameConfig(title="Demo"))
    assert no_title.tobytes() != with_title.tobytes()


def test_watermark_none_returns_unchanged():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_watermark(base, FrameConfig(watermark=None))
    assert result.tobytes() == base.tobytes()


def test_watermark_text_modifies_image():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_watermark
    base = Image.new("RGBA", (200, 200), (20, 20, 20, 255))
    result = _apply_watermark(base, FrameConfig(watermark="scriptcast", watermark_size=14))
    assert result.tobytes() != base.tobytes()


def test_apply_frame_increases_canvas_size(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import TITLE_BAR_HEIGHT, apply_frame

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=100, height=60)

    config = FrameConfig(
        margin_top=50, margin_right=50, margin_bottom=50, margin_left=50,
        padding_top=10, padding_right=10, padding_bottom=10, padding_left=10,
        shadow=False,
    )
    apply_frame(gif_path, config)

    result = Image.open(gif_path)
    assert result.width == 100 + 2 * 10 + 2 * 50
    assert result.height == 60 + 2 * 10 + TITLE_BAR_HEIGHT + 2 * 50


def test_apply_frame_preserves_frame_count(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)  # 2 frames

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ))

    result = Image.open(gif_path)
    count = 0
    try:
        while True:
            count += 1
            result.seek(result.tell() + 1)
    except EOFError:
        pass
    assert count == 2


def test_apply_frame_missing_pillow(tmp_path, monkeypatch):
    import builtins
    import sys

    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame

    gif_path = tmp_path / "test.gif"
    gif_path.write_bytes(b"GIF89a")

    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("PIL"):
            raise ImportError("No module named 'PIL'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    for key in list(sys.modules):
        if key.startswith("PIL"):
            monkeypatch.delitem(sys.modules, key)

    with pytest.raises(RuntimeError, match="Pillow"):
        apply_frame(gif_path, FrameConfig())


def test_build_global_palette_returns_p_mode_image():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.frame import _build_global_palette

    template = Image.new("RGB", (100, 50), (30, 30, 30))
    frames = [Image.new("RGB", (100, 50), (i * 10, 0, 0)) for i in range(5)]
    palette_ref = _build_global_palette(template, frames)

    assert palette_ref.mode == "P"


def test_build_global_palette_samples_at_most_max_samples():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.frame import _build_global_palette

    # Build 50 frames; helper should still return without error and produce P-mode image
    template = Image.new("RGB", (40, 20), (30, 30, 30))
    frames = [Image.new("RGB", (40, 20), (i % 255, i % 255, i % 255)) for i in range(50)]
    palette_ref = _build_global_palette(template, frames, max_samples=20)

    assert palette_ref.mode == "P"


def test_build_global_palette_single_frame():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.frame import _build_global_palette

    template = Image.new("RGB", (40, 20), (30, 30, 30))
    frames = [Image.new("RGB", (40, 20), (200, 100, 50))]
    palette_ref = _build_global_palette(template, frames)

    assert palette_ref.mode == "P"


def test_build_global_palette_chrome_colors_exact():
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.frame import _CHROME_COLORS, _build_global_palette

    template = Image.new("RGB", (100, 50), (30, 30, 30))
    frames = [Image.new("RGB", (100, 50), (i * 10, 200, 100)) for i in range(5)]
    palette_ref = _build_global_palette(template, frames)

    raw = palette_ref.getpalette()  # R,G,B per slot; length varies with content variety
    for i, (r, g, b) in enumerate(_CHROME_COLORS):
        assert raw[i * 3] == r, f"slot {i} R mismatch"
        assert raw[i * 3 + 1] == g, f"slot {i} G mismatch"
        assert raw[i * 3 + 2] == b, f"slot {i} B mismatch"


def _make_colorful_gif(path, width=160, height=80):
    """Create a 2-frame GIF with thousands of distinct colors to stress palette quantization.

    Frame 1 and Frame 2 have different color gradients, so independent per-frame
    quantization would produce different optimal palettes.
    """
    from PIL import Image

    data1 = bytes(
        val
        for y in range(height)
        for x in range(width)
        for val in ((x * 3) % 256, (y * 3) % 256, ((x + y) * 2) % 256)
    )
    f1 = Image.frombytes("RGB", (width, height), data1)

    data2 = bytes(
        val
        for y in range(height)
        for x in range(width)
        for val in ((x * 3 + 100) % 256, (y * 3 + 50) % 256, ((x + y) * 2 + 150) % 256)
    )
    f2 = Image.frombytes("RGB", (width, height), data2)

    f1.quantize(colors=256).save(
        path, save_all=True, append_images=[f2.quantize(colors=256)], duration=100, loop=0
    )


def test_apply_frame_palette_is_shared(tmp_path):
    """Stable locations (title bar / window chrome) must have identical pixels across frames."""
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import TITLE_BAR_HEIGHT, apply_frame

    gif_path = tmp_path / "test.gif"
    _make_colorful_gif(gif_path, width=160, height=80)
    config = FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10,
        padding_top=4, padding_right=8, padding_bottom=4, padding_left=8,
        shadow=False, radius=0,
    )
    apply_frame(gif_path, config)

    img = Image.open(gif_path)
    stable_x = 10 + 120
    stable_y = 10 + TITLE_BAR_HEIGHT // 2

    frame_pixels = []
    try:
        while True:
            frame_pixels.append(img.convert("RGB").getpixel((stable_x, stable_y)))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    assert len(frame_pixels) == 2
    assert frame_pixels[0] == frame_pixels[1], (
        f"title bar color changed between frames: {frame_pixels}"
    )


def test_apply_frame_traffic_light_color_stable(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from scriptcast.config import FrameConfig
    from scriptcast.frame import _TRAFFIC_LIGHTS, TITLE_BAR_HEIGHT, apply_frame

    gif_path = tmp_path / "test.gif"
    _make_colorful_gif(gif_path, width=160, height=80)
    config = FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10,
        padding_top=4, padding_right=8, padding_bottom=4, padding_left=8,
        shadow=False, radius=0,
    )
    apply_frame(gif_path, config)

    img = Image.open(gif_path)
    window_x = 10
    y_center = 10 + TITLE_BAR_HEIGHT // 2
    red_light_x = window_x + _TRAFFIC_LIGHTS[0][0]

    pixel_per_frame = []
    try:
        while True:
            pixel_per_frame.append(img.convert("RGB").getpixel((red_light_x, y_center)))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    assert len(pixel_per_frame) == 2
    assert pixel_per_frame[0] == pixel_per_frame[1], (
        f"red traffic light color changed between frames: {pixel_per_frame}"
    )


def test_scriptcast_watermark_disabled_returns_unchanged():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_scriptcast_watermark
    base = Image.new("RGBA", (300, 100), (20, 20, 20, 255))
    result = _apply_scriptcast_watermark(base, FrameConfig(scriptcast_watermark=False))
    assert result.tobytes() == base.tobytes()


def test_scriptcast_watermark_enabled_modifies_image():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_scriptcast_watermark
    base = Image.new("RGBA", (300, 100), (20, 20, 20, 255))
    result = _apply_scriptcast_watermark(base, FrameConfig(scriptcast_watermark=True))
    assert result.tobytes() != base.tobytes()


def test_apply_frame_includes_scriptcast_watermark(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    import shutil

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=100, height=60)

    # With watermark (default)
    gif_wm = tmp_path / "with_wm.gif"
    shutil.copy(gif_path, gif_wm)
    apply_frame(gif_wm, FrameConfig())

    # Without watermark
    gif_no_wm = tmp_path / "no_wm.gif"
    shutil.copy(gif_path, gif_no_wm)
    apply_frame(gif_no_wm, FrameConfig(scriptcast_watermark=False))

    wm_data = Image.open(gif_wm).tobytes()
    no_wm_data = Image.open(gif_no_wm).tobytes()
    assert wm_data != no_wm_data


def test_apply_scriptcast_watermark_standalone(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_scriptcast_watermark

    gif_path = tmp_path / "raw.gif"
    _make_tiny_gif(gif_path, width=200, height=80)

    original_size = Image.open(gif_path).size
    apply_scriptcast_watermark(gif_path, FrameConfig())
    result_size = Image.open(gif_path).size

    # Canvas size must not change
    assert result_size == original_size

    # Pixels must differ (watermark was drawn)
    # Re-make original for comparison
    _make_tiny_gif(tmp_path / "ref.gif", width=200, height=80)
    ref_bytes = Image.open(tmp_path / "ref.gif").tobytes()
    result_bytes = Image.open(gif_path).tobytes()
    assert result_bytes != ref_bytes


def test_apply_frame_watermark_over_terminal_content(tmp_path):
    """Watermark must be drawn on top of terminal content, not behind it."""
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame

    # GIF filled entirely with red — easy to distinguish from the white watermark text
    gif_path = tmp_path / "red.gif"
    from PIL import Image as _Image
    red = _Image.new("RGB", (300, 100), (255, 0, 0))
    red.quantize(colors=256).save(gif_path, save_all=True, duration=100, loop=0)

    config = FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=0, border_width=0,
        scriptcast_watermark=True,
    )
    apply_frame(gif_path, config)

    result = Image.open(gif_path).convert("RGB")
    # Bottom-right corner should not be all red — watermark pixels are there
    corner_pixels = [result.getpixel((x, y)) for x in range(280, 300) for y in range(85, 100)]
    assert any(r != 255 or g != 0 or b != 0 for r, g, b in corner_pixels), (
        "Expected watermark pixels at bottom-right, but all pixels were red (content color)"
    )


def test_scriptcast_watermark_text_is_scriptcast():
    """Watermark text is 'ScriptCast' (capital S and C)."""
    import scriptcast.frame as frame_mod
    assert frame_mod._WATERMARK_TEXT == "ScriptCast"


# ---------------------------------------------------------------------------
# SVG rendering path (cairosvg mocked)
# ---------------------------------------------------------------------------

def _make_fake_cairosvg(canvas_w: int, canvas_h: int):
    """Return a fake cairosvg module whose svg2png returns a solid-grey RGBA PNG."""
    import io
    import re
    import types

    fake = types.ModuleType("cairosvg")

    def svg2png(bytestring: bytes) -> bytes:  # noqa: ANN001
        svg_str = bytestring.decode()
        w = int(re.search(r'width="(\d+)"', svg_str).group(1))
        h = int(re.search(r'height="(\d+)"', svg_str).group(1))
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGBA", (w, h), (30, 30, 30, 255)).save(buf, format="PNG")
        return buf.getvalue()

    fake.svg2png = svg2png
    return fake


def test_apply_frame_svg_path_canvas_size(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import TITLE_BAR_HEIGHT, apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=100, height=60)

    config = FrameConfig(
        margin_top=50, margin_right=50, margin_bottom=50, margin_left=50,
        padding_top=10, padding_right=10, padding_bottom=10, padding_left=10,
        shadow=False,
    )
    apply_frame(gif_path, config)

    result = Image.open(gif_path)
    assert result.width == 100 + 2 * 10 + 2 * 50
    assert result.height == 60 + 2 * 10 + TITLE_BAR_HEIGHT + 2 * 50


def test_apply_frame_svg_path_preserves_frame_count(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)  # 2 frames

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ))

    img = Image.open(gif_path)
    count = 0
    try:
        while True:
            count += 1
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    assert count == 2


def test_apply_frame_svg_path_watermark_over_content(tmp_path, monkeypatch):
    """Watermark must appear on top of terminal content even in SVG path."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image as _Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    gif_path = tmp_path / "red.gif"
    red = _Image.new("RGB", (300, 100), (255, 0, 0))
    red.quantize(colors=256).save(gif_path, save_all=True, duration=100, loop=0)

    config = FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=0, border_width=0,
        scriptcast_watermark=True,
    )
    apply_frame(gif_path, config)

    result = _Image.open(gif_path).convert("RGB")
    corner_pixels = [result.getpixel((x, y)) for x in range(280, 300) for y in range(85, 100)]
    assert any(r != 255 or g != 0 or b != 0 for r, g, b in corner_pixels), (
        "Watermark pixels expected at bottom-right, all pixels were red"
    )


# ---------------------------------------------------------------------------
# APNG output
# ---------------------------------------------------------------------------

def test_apply_frame_apng_writes_png_file(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ), format="apng")

    png_path = gif_path.with_suffix(".png")
    assert png_path.exists(), "Expected .png file to be written for apng format"


def test_apply_frame_apng_preserves_frame_count(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)  # 2 frames

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ), format="apng")

    img = Image.open(gif_path.with_suffix(".png"))
    count = 0
    try:
        while True:
            count += 1
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    assert count == 2


def test_apply_frame_apng_is_full_color(tmp_path, monkeypatch):
    """APNG frames must not be quantized — pixels retain full RGB values."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    # Bright red terminal frame — easy to detect if color is preserved
    red = Image.new("RGB", (60, 40), (200, 50, 30))
    gif_path = tmp_path / "red.gif"
    red.quantize(colors=256).save(gif_path, duration=100, loop=0)

    apply_frame(gif_path, FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=0, border_width=0,
        scriptcast_watermark=False,
    ), format="apng")

    png_path = gif_path.with_suffix(".png")
    result = Image.open(png_path).convert("RGB")
    # Mode must be full color, not palette
    assert result.mode in ("RGB", "RGBA"), f"Unexpected mode: {result.mode}"


def test_apply_frame_apng_pil_fallback_writes_png(tmp_path, monkeypatch):
    """PIL fallback must write a .png file when format='apng', even without cairosvg."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame

    monkeypatch.setattr(frame_mod, "_svg_available", False)

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ), format="apng")

    assert gif_path.with_suffix(".png").exists(), "Expected .png for apng format in PIL fallback"


def test_apply_frame_apng_pil_fallback_frame_count(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", False)

    gif_path = tmp_path / "test.gif"
    _make_tiny_gif(gif_path, width=40, height=20)  # 2 frames

    apply_frame(gif_path, FrameConfig(
        margin_top=10, margin_right=10, margin_bottom=10, margin_left=10, shadow=False
    ), format="apng")

    img = Image.open(gif_path.with_suffix(".png"))
    count = 0
    try:
        while True:
            count += 1
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    assert count == 2


def test_apply_frame_apng_pil_fallback_full_color(tmp_path, monkeypatch):
    """PIL APNG frames must not be quantized."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image

    monkeypatch.setattr(frame_mod, "_svg_available", False)

    red = Image.new("RGB", (60, 40), (200, 50, 30))
    gif_path = tmp_path / "red.gif"
    red.quantize(colors=256).save(gif_path, duration=100, loop=0)

    apply_frame(gif_path, FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=0, border_width=0, scriptcast_watermark=False,
    ), format="apng")

    result = Image.open(gif_path.with_suffix(".png")).convert("RGB")
    assert result.mode in ("RGB", "RGBA"), f"Unexpected mode: {result.mode}"


def test_make_content_mask_returns_l_mode():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    mask = _make_content_mask((200, 150), 10, 30, 100, 80, radius=0)
    assert mask.mode == "L"
    assert mask.size == (200, 150)


def test_make_content_mask_center_is_white():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    mask = _make_content_mask((200, 150), 10, 30, 100, 80, radius=0)
    # Centre of content area
    assert mask.getpixel((60, 70)) == 255


def test_make_content_mask_outside_is_black():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    mask = _make_content_mask((200, 150), 10, 30, 100, 80, radius=0)
    # Pixel outside content area (left of it)
    assert mask.getpixel((5, 70)) == 0
    # Pixel above content area
    assert mask.getpixel((60, 5)) == 0


def test_make_content_mask_bottom_corner_rounded():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    # content at (0,0), 100x60, radius=20 — bottom-left corner pixel should be masked
    mask = _make_content_mask((100, 60), 0, 0, 100, 60, radius=20)
    assert mask.getpixel((0, 59)) == 0   # bottom-left corner, inside the arc


def test_make_content_mask_top_corners_not_rounded():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    # radius=20 but top corners must remain straight (flat edge at title bar separator)
    mask = _make_content_mask((100, 60), 0, 0, 100, 60, radius=20)
    assert mask.getpixel((0, 0)) == 255   # top-left — must NOT be clipped
    assert mask.getpixel((99, 0)) == 255  # top-right — must NOT be clipped


def test_make_content_mask_right_and_bottom_edges_are_white():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    mask = _make_content_mask((200, 150), 10, 30, 100, 80, radius=0)
    # Rightmost column of content area
    assert mask.getpixel((109, 70)) == 255   # content_x + content_w - 1 = 10 + 100 - 1 = 109
    # Bottom row of content area
    assert mask.getpixel((60, 109)) == 255   # content_y + content_h - 1 = 30 + 80 - 1 = 109


def test_make_content_mask_offset_with_radius():
    pytest.importorskip("PIL")
    from scriptcast.frame import _make_content_mask
    # Non-zero offset + radius — the realistic production case
    mask = _make_content_mask((200, 150), 20, 40, 100, 80, radius=10)
    # Centre is white
    assert mask.getpixel((70, 80)) == 255    # content_x + content_w//2, content_y + content_h//2
    # Bottom-left corner is clipped (rounded)
    assert mask.getpixel((20, 119)) == 0     # content_x, content_y + content_h - 1
    # Top-left corner is straight (not clipped)
    assert mask.getpixel((20, 40)) == 255    # content_x, content_y


def test_apply_frame_svg_path_corner_not_terminal_color(tmp_path, monkeypatch):
    """With radius>0 and padding=0, bottom-left corner must not be the terminal fill colour."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image as _Image

    monkeypatch.setattr(frame_mod, "_svg_available", True)
    monkeypatch.setattr(frame_mod, "_cairosvg", _make_fake_cairosvg(0, 0))

    # Bright red terminal frame — easy to detect bleed
    red = _Image.new("RGB", (80, 60), (200, 0, 0))
    gif_path = tmp_path / "red.gif"
    red.quantize(colors=256).save(gif_path, duration=100, loop=0)

    config = FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=12, border_width=0,
        scriptcast_watermark=False,
    )
    apply_frame(gif_path, config)

    result = _Image.open(gif_path).convert("RGB")
    # Bottom-left corner of the full canvas — window radius clips this pixel
    r, g, b = result.getpixel((0, result.height - 1))
    assert not (r > 150 and g < 50 and b < 50), (
        "Bottom-left corner is terminal red — content is bleeding outside rounded window"
    )


# ---------------------------------------------------------------------------
# Task 5: _draw_gradient_circle unit tests
# ---------------------------------------------------------------------------

def test_draw_gradient_circle_center_is_highlight():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.frame import _draw_gradient_circle

    img = Image.new("RGBA", (40, 40), (30, 30, 30, 255))
    _draw_gradient_circle(img, 20, 20, 6, "#FF5F57", "#FF8C80")
    r, g, b, a = img.getpixel((20, 20))
    # Centre should be close to highlight #FF8C80 = (255, 140, 128)
    assert r > 200 and g > 100 and b > 100


def test_draw_gradient_circle_edge_is_darker_than_center():
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.frame import _draw_gradient_circle

    img = Image.new("RGBA", (40, 40), (30, 30, 30, 255))
    _draw_gradient_circle(img, 20, 20, 6, "#FF5F57", "#FF8C80")
    r_center, g_center, _, _ = img.getpixel((20, 20))
    r_edge, g_edge, _, _ = img.getpixel((26, 20))  # rightmost edge pixel
    # Edge green channel should be less than or equal to centre (dimmer)
    assert g_edge <= g_center


# ---------------------------------------------------------------------------
# Task 4: titlebar background colour test
# ---------------------------------------------------------------------------

def test_title_bar_bg_is_titlebar_color():
    """The title bar area should be filled with #252535, not the window bg #1E1E1E."""
    pytest.importorskip("PIL")
    from PIL import Image
    from scriptcast.config import FrameConfig
    from scriptcast.frame import _apply_title_bar

    # Window fill is pure black so any non-black pixel in titlebar area is the titlebar colour
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    result = _apply_title_bar(base, 0, 0, 200, 200, FrameConfig(radius=0))
    # Middle of the title bar, away from traffic lights
    r, g, b, a = result.getpixel((150, 14))
    assert (r, g, b) == (0x25, 0x25, 0x35), (
        f"Expected titlebar colour #252535, got ({r:#x}, {g:#x}, {b:#x})"
    )


# ---------------------------------------------------------------------------
# Task 3: PIL fallback content masking
# ---------------------------------------------------------------------------

def test_apply_frame_pil_fallback_corner_not_terminal_color(tmp_path, monkeypatch):
    """PIL path: with radius>0 and padding=0, bottom-left corner must not be terminal colour."""
    pytest.importorskip("PIL")
    import scriptcast.frame as frame_mod
    from scriptcast.config import FrameConfig
    from scriptcast.frame import apply_frame
    from PIL import Image as _Image

    monkeypatch.setattr(frame_mod, "_svg_available", False)

    red = _Image.new("RGB", (80, 60), (200, 0, 0))
    gif_path = tmp_path / "red.gif"
    red.quantize(colors=256).save(gif_path, duration=100, loop=0)

    config = FrameConfig(
        margin_top=0, margin_right=0, margin_bottom=0, margin_left=0,
        padding_top=0, padding_right=0, padding_bottom=0, padding_left=0,
        shadow=False, radius=12, border_width=0,
        scriptcast_watermark=False,
    )
    apply_frame(gif_path, config)

    result = _Image.open(gif_path).convert("RGB")
    r, g, b = result.getpixel((0, result.height - 1))
    assert not (r > 150 and g < 50 and b < 50), (
        "Bottom-left corner is terminal red — PIL fallback content is bleeding outside window"
    )
