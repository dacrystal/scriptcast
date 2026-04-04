# tests/test_theme.py
"""Tests for theme-related behaviour after theme.py deletion.

Theme config is now built via ScriptcastConfig.apply() and ThemeConfig.apply().
Loading a theme .sh file runs through the recorder pipeline (tested in integration).
"""
import json

import pytest


# --- ThemeConfig.apply() via ScriptcastConfig ---

def test_sc_apply_theme_background():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-background", "1a1a2e,16213e"])
    assert sc.theme.background == "1a1a2e,16213e"


def test_sc_apply_theme_radius():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-radius", "16"])
    assert sc.theme.radius == 16


def test_sc_apply_theme_shadow_false():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-shadow", "false"])
    assert sc.theme.shadow is False


def test_sc_apply_theme_margin_one_value():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-margin", "60"])
    assert sc.theme.margin_top == 60
    assert sc.theme.margin_right == 60
    assert sc.theme.margin_bottom == 60
    assert sc.theme.margin_left == 60


def test_sc_apply_theme_margin_two_values():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-margin", "82 40"])
    assert sc.theme.margin_top == 82
    assert sc.theme.margin_right == 40
    assert sc.theme.margin_bottom == 82
    assert sc.theme.margin_left == 40


def test_sc_apply_theme_margin_three_values():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-margin", "82 82 120"])
    assert sc.theme.margin_top == 82
    assert sc.theme.margin_right == 82
    assert sc.theme.margin_bottom == 120
    assert sc.theme.margin_left == 82


def test_sc_apply_theme_margin_individual_side():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-margin-bottom", "120"])
    assert sc.theme.margin_bottom == 120
    assert sc.theme.margin_top is None


def test_sc_apply_theme_padding_one_value():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-padding", "20"])
    assert sc.theme.padding_top == 20
    assert sc.theme.padding_right == 20
    assert sc.theme.padding_bottom == 20
    assert sc.theme.padding_left == 20


def test_sc_apply_theme_padding_two_values():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-padding", "10 20"])
    assert sc.theme.padding_top == 10
    assert sc.theme.padding_right == 20
    assert sc.theme.padding_bottom == 10
    assert sc.theme.padding_left == 20


def test_sc_apply_theme_padding_individual_side():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-padding-top", "8"])
    assert sc.theme.padding_top == 8
    assert sc.theme.padding_right == 14  # unchanged default


def test_sc_apply_theme_frame_true():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-frame", "true"])
    assert sc.theme.frame is True


def test_sc_apply_theme_frame_false():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-frame", "false"])
    assert sc.theme.frame is False


def test_sc_apply_terminal_theme():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["terminal-theme", "monokai"])
    assert sc.terminal_theme == "monokai"


def test_sc_apply_theme_frame_bar_title():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-frame-bar-title", "Terminal"])
    assert sc.theme.frame_bar_title == "Terminal"


def test_sc_apply_theme_scriptcast_watermark_false():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-scriptcast-watermark", "false"])
    assert sc.theme.scriptcast_watermark is False


# --- CSS shorthand helper (now in config.py) ---

def test_parse_css_shorthand_one_value():
    from scriptcast.config import _parse_css_shorthand
    assert _parse_css_shorthand("82") == (82, 82, 82, 82)


def test_parse_css_shorthand_two_values():
    from scriptcast.config import _parse_css_shorthand
    assert _parse_css_shorthand("82 40") == (82, 40, 82, 40)


def test_parse_css_shorthand_three_values():
    from scriptcast.config import _parse_css_shorthand
    assert _parse_css_shorthand("82 40 120") == (82, 40, 120, 40)


def test_parse_css_shorthand_four_values():
    from scriptcast.config import _parse_css_shorthand
    assert _parse_css_shorthand("82 40 120 60") == (82, 40, 120, 60)


def test_parse_css_shorthand_invalid_raises():
    from scriptcast.config import _parse_css_shorthand
    with pytest.raises(ValueError, match="1-4"):
        _parse_css_shorthand("10 20 30 40 50")


def test_parse_css_shorthand_multi_value_margin():
    from scriptcast.config import _parse_css_shorthand
    assert _parse_css_shorthand("82 82 120") == (82, 82, 120, 82)


# --- build_config_from_sc_text: theme keys from .sc ---

def test_sc_file_with_theme_directives_builds_theme_config():
    from scriptcast.generator import build_config_from_sc_text
    header = json.dumps({"version": 1, "width": 100, "height": 28, "directive-prefix": "SC"})
    events = [
        json.dumps([0.0, "directive", "set theme-background ff0000,0000ff"]),
        json.dumps([0.1, "directive", "set theme-radius 16"]),
        json.dumps([0.2, "directive", "set terminal-theme light"]),
    ]
    sc = header + "\n" + "\n".join(events)
    cfg = build_config_from_sc_text(sc)
    assert cfg.theme.background == "ff0000,0000ff"
    assert cfg.theme.radius == 16
    assert cfg.terminal_theme == "light"


def test_sc_file_theme_and_script_config():
    from scriptcast.generator import build_config_from_sc_text
    header = json.dumps({"version": 1, "width": 100, "height": 28, "directive-prefix": "SC"})
    events = [
        json.dumps([0.0, "directive", "set type_speed 30"]),
        json.dumps([0.1, "directive", "set theme-frame false"]),
    ]
    sc = header + "\n" + "\n".join(events)
    cfg = build_config_from_sc_text(sc)
    assert cfg.type_speed == 30
    assert cfg.theme.frame is False


def test_sc_file_multi_value_padding():
    from scriptcast.generator import build_config_from_sc_text
    header = json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"})
    sc = header + "\n" + json.dumps([0.0, "directive", "set theme-padding 14 0 0 0"])
    cfg = build_config_from_sc_text(sc)
    assert cfg.theme.padding_top == 14
    assert cfg.theme.padding_right == 0
