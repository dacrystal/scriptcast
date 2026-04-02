# tests/test_theme.py
import json
from pathlib import Path

import pytest


def test_parse_theme_file(tmp_path):
    from scriptcast.theme import parse_theme_file
    f = tmp_path / "mytheme.sh"
    f.write_text(
        ": SC set theme-background #1a1a2e\n"
        ": SC set theme-radius 16\n"
        ": SC set theme-shadow true\n"
        "# a comment\n"
        "echo hello\n"
    )
    result = parse_theme_file(f)
    assert result == {
        "theme-background": "#1a1a2e",
        "theme-radius": "16",
        "theme-shadow": "true",
    }


def test_parse_theme_file_ignores_non_set_lines(tmp_path):
    from scriptcast.theme import parse_theme_file
    f = tmp_path / "t.sh"
    f.write_text(": SC mock ls\n: SC set theme-margin 82\n")
    result = parse_theme_file(f)
    assert result == {"theme-margin": "82"}


def test_load_theme_builtin():
    from scriptcast.theme import load_theme
    result = load_theme("dark")
    # dark.sh must exist and define at least one key
    assert isinstance(result, dict)
    assert len(result) > 0


def test_load_theme_file(tmp_path):
    from scriptcast.theme import load_theme
    f = tmp_path / "custom.sh"
    f.write_text(": SC set theme-radius 20\n")
    result = load_theme(str(f))
    assert result == {"theme-radius": "20"}


def test_load_theme_missing_raises():
    from scriptcast.theme import load_theme
    with pytest.raises(FileNotFoundError):
        load_theme("nonexistent_theme_xyz")


def test_apply_theme_string_property(tmp_path):
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    sc = ScriptcastConfig()
    apply_theme_to_configs({"theme-background": "#001122"}, fc, sc)
    assert fc.background == "#001122"


def test_apply_theme_int_property():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    sc = ScriptcastConfig()
    apply_theme_to_configs({"theme-radius": "20"}, fc, sc)
    assert fc.radius == 20


def test_apply_theme_bool_property():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    sc = ScriptcastConfig()
    apply_theme_to_configs({"theme-shadow": "false"}, fc, sc)
    assert fc.shadow is False


def test_apply_theme_margin_one_value():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-margin": "60"}, fc, ScriptcastConfig())
    assert fc.margin_top == 60
    assert fc.margin_right == 60
    assert fc.margin_bottom == 60
    assert fc.margin_left == 60


def test_apply_theme_margin_two_values():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-margin": "82 40"}, fc, ScriptcastConfig())
    assert fc.margin_top == 82
    assert fc.margin_right == 40
    assert fc.margin_bottom == 82
    assert fc.margin_left == 40


def test_apply_theme_margin_three_values():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-margin": "82 82 120"}, fc, ScriptcastConfig())
    assert fc.margin_top == 82
    assert fc.margin_right == 82
    assert fc.margin_bottom == 120
    assert fc.margin_left == 82


def test_apply_theme_margin_individual_side():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-margin-bottom": "120"}, fc, ScriptcastConfig())
    assert fc.margin_bottom == 120
    assert fc.margin_top is None  # unchanged


def test_apply_theme_padding_one_value():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-padding": "20"}, fc, ScriptcastConfig())
    assert fc.padding_top == 20
    assert fc.padding_right == 20
    assert fc.padding_bottom == 20
    assert fc.padding_left == 20


def test_apply_theme_padding_two_values():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-padding": "10 20"}, fc, ScriptcastConfig())
    assert fc.padding_top == 10
    assert fc.padding_right == 20
    assert fc.padding_bottom == 10
    assert fc.padding_left == 20


def test_apply_theme_padding_individual_side():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-padding-top": "8"}, fc, ScriptcastConfig())
    assert fc.padding_top == 8
    assert fc.padding_right == 14  # unchanged default


def test_apply_theme_frame_macos():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    apply_theme_to_configs({"theme-frame": "macos"}, fc, ScriptcastConfig())
    assert fc.frame == "macos"


def test_apply_theme_frame_none():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig(frame="macos")
    apply_theme_to_configs({"theme-frame": "none"}, fc, ScriptcastConfig())
    # `frame` is typed as `str` (non-nullable), so the string "none" is preserved as-is
    # rather than being converted to Python None.
    assert fc.frame == "none"


def test_apply_terminal_theme():
    from scriptcast.config import FrameConfig, ScriptcastConfig
    from scriptcast.theme import apply_theme_to_configs
    fc = FrameConfig()
    sc = ScriptcastConfig()
    apply_theme_to_configs({"terminal-theme": "monokai"}, fc, sc)
    assert sc.terminal_theme == "monokai"


def test_scan_sc_for_theme(tmp_path):
    from scriptcast.theme import scan_sc_for_theme
    sc_file = tmp_path / "demo.sc"
    lines = [
        json.dumps({"directive-prefix": "SC", "width": 100, "height": 28}),
        json.dumps([0.0, "directive", "set theme-background #333333"]),
        json.dumps([0.1, "directive", "set type_speed 50"]),
        json.dumps([0.2, "directive", "set theme-radius 16"]),
        json.dumps([0.3, "cmd", "echo hello"]),
    ]
    sc_file.write_text("\n".join(lines))
    result = scan_sc_for_theme(sc_file)
    assert result == {"theme-background": "#333333", "theme-radius": "16"}


def test_scan_sc_ignores_non_theme_set():
    from pathlib import Path
    import json, tempfile
    from scriptcast.theme import scan_sc_for_theme
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sc", delete=False) as f:
        f.write(json.dumps({"directive-prefix": "SC"}) + "\n")
        f.write(json.dumps([0.0, "directive", "set type_speed 60"]) + "\n")
        p = Path(f.name)
    result = scan_sc_for_theme(p)
    assert result == {}
    p.unlink()


def test_parse_css_shorthand_one_value():
    from scriptcast.theme import _parse_css_shorthand
    assert _parse_css_shorthand("82") == (82, 82, 82, 82)


def test_parse_css_shorthand_two_values():
    from scriptcast.theme import _parse_css_shorthand
    assert _parse_css_shorthand("82 40") == (82, 40, 82, 40)


def test_parse_css_shorthand_three_values():
    from scriptcast.theme import _parse_css_shorthand
    # top=82, right/left=40, bottom=120
    assert _parse_css_shorthand("82 40 120") == (82, 40, 120, 40)


def test_parse_css_shorthand_four_values():
    from scriptcast.theme import _parse_css_shorthand
    assert _parse_css_shorthand("82 40 120 60") == (82, 40, 120, 60)


def test_parse_css_shorthand_invalid_raises():
    from scriptcast.theme import _parse_css_shorthand
    with pytest.raises(ValueError, match="1-4"):
        _parse_css_shorthand("10 20 30 40 50")
