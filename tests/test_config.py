# tests/test_config.py
from scriptcast.config import ScriptcastConfig


def test_defaults():
    c = ScriptcastConfig()
    assert c.type_speed == 40
    assert c.cmd_wait == 80
    assert c.input_wait == 80
    assert c.exit_wait == 120
    assert c.enter_wait == 80
    assert c.width == 100
    assert c.height == 28
    assert c.terminal_theme == "dark"    # was c.theme
    assert c.prompt == "$ "
    assert c.directive_prefix == "SC"
    assert c.trace_prefix == "+"
    assert c.split_scenes is False

def test_apply_set_int():
    c = ScriptcastConfig()
    c.apply("set", ["type_speed", "60"])
    assert c.type_speed == 60

def test_apply_set_str():
    c = ScriptcastConfig()
    c.apply("set", ["terminal-theme", "light"])   # dash form; was "theme"
    assert c.terminal_theme == "light"             # was c.theme

def test_apply_old_theme_key_ignored():
    c = ScriptcastConfig()
    c.apply("set", ["theme", "light"])   # old key — no longer valid
    assert c.terminal_theme == "dark"   # unchanged

def test_apply_unknown_key_ignored():
    c = ScriptcastConfig()
    c.apply("set", ["nonexistent", "value"])  # must not raise

def test_apply_non_set_directive_ignored():
    c = ScriptcastConfig()
    c.apply("scene", ["Intro"])  # must not raise

def test_copy_is_independent():
    c = ScriptcastConfig()
    c2 = c.copy()
    c2.type_speed = 999
    assert c.type_speed == 40

def test_enter_wait_default():
    assert ScriptcastConfig().enter_wait == 80

def test_input_wait_default_is_cmd_wait():
    assert ScriptcastConfig().input_wait == 80

def test_split_scenes_default():
    assert ScriptcastConfig().split_scenes is False

def test_apply_enter_wait():
    c = ScriptcastConfig()
    c.apply("set", ["enter_wait", "200"])
    assert c.enter_wait == 200

def test_apply_split_scenes_true():
    c = ScriptcastConfig()
    c.apply("set", ["split_scenes", "true"])
    assert c.split_scenes is True

def test_apply_split_scenes_false():
    c = ScriptcastConfig()
    c.split_scenes = True
    c.apply("set", ["split_scenes", "false"])
    assert c.split_scenes is False

def test_word_speed_default_is_none():
    assert ScriptcastConfig().word_speed is None

def test_apply_word_speed():
    c = ScriptcastConfig()
    c.apply("set", ["word_speed", "80"])
    assert c.word_speed == 80


def test_theme_config_defaults():
    from scriptcast.config import ThemeConfig
    c = ThemeConfig()
    assert c.frame_bar_title == ""
    # Individual padding sides
    assert c.padding_top == 14
    assert c.padding_right == 14
    assert c.padding_bottom == 14
    assert c.padding_left == 14
    assert c.radius == 12
    assert c.border_color == "ffffff30"
    assert c.border_width == 1
    assert c.background == "1e1b4b,0d3b66"
    # Individual margin sides
    assert c.margin_top is None
    assert c.margin_right is None
    assert c.margin_bottom is None
    assert c.margin_left is None
    assert c.shadow is True
    assert c.shadow_color == "0000004d"
    assert c.shadow_radius == 20
    assert c.shadow_offset_y == 21
    assert c.watermark is None
    assert c.watermark_color == "ffffff"
    assert c.watermark_size is None
    assert c.scriptcast_watermark is True
    assert c.frame is True


def test_theme_config_custom():
    from scriptcast.config import ThemeConfig
    c = ThemeConfig(frame_bar_title="Demo", background="#1a1a2e,#16213e", watermark="hello")
    assert c.frame_bar_title == "Demo"
    assert c.background == "#1a1a2e,#16213e"
    assert c.watermark == "hello"


def test_theme_config_custom_padding():
    from scriptcast.config import ThemeConfig
    c = ThemeConfig(padding_top=10, padding_right=20, padding_bottom=30, padding_left=20)
    assert c.padding_top == 10
    assert c.padding_bottom == 30


def test_theme_config_custom_margin():
    from scriptcast.config import ThemeConfig
    c = ThemeConfig(margin_top=40, margin_bottom=80)
    assert c.margin_top == 40
    assert c.margin_bottom == 80
    assert c.margin_left is None


def test_theme_config_frame_default_true():
    from scriptcast.config import ThemeConfig
    assert ThemeConfig().frame is True

def test_theme_config_frame_true():
    from scriptcast.config import ThemeConfig
    assert ThemeConfig(frame=True).frame is True


def test_theme_config_scriptcast_watermark_default():
    from scriptcast.config import ThemeConfig
    assert ThemeConfig().scriptcast_watermark is True

def test_theme_config_scriptcast_watermark_disabled():
    from scriptcast.config import ThemeConfig
    assert ThemeConfig(scriptcast_watermark=False).scriptcast_watermark is False


def test_theme_config_apply_string():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("background", "ff0000,0000ff")
    assert tc.background == "ff0000,0000ff"

def test_theme_config_apply_int():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("radius", "20")
    assert tc.radius == 20

def test_theme_config_apply_bool_true():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig(shadow=False)
    tc.apply("shadow", "true")
    assert tc.shadow is True

def test_theme_config_apply_bool_false():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig(frame=True)
    tc.apply("frame", "false")
    assert tc.frame is False

def test_theme_config_apply_bool_scriptcast_watermark():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig(scriptcast_watermark=True)
    tc.apply("scriptcast-watermark", "false")
    assert tc.scriptcast_watermark is False

def test_theme_config_apply_margin_shorthand_one():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("margin", "60")
    assert (tc.margin_top, tc.margin_right, tc.margin_bottom, tc.margin_left) == (60, 60, 60, 60)

def test_theme_config_apply_margin_shorthand_three():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("margin", "32 32 64")
    assert tc.margin_top == 32
    assert tc.margin_right == 32
    assert tc.margin_bottom == 64
    assert tc.margin_left == 32

def test_theme_config_apply_padding_shorthand():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("padding", "10 20")
    assert (tc.padding_top, tc.padding_bottom) == (10, 10)
    assert (tc.padding_left, tc.padding_right) == (20, 20)

def test_theme_config_apply_margin_individual():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("margin-bottom", "120")
    assert tc.margin_bottom == 120
    assert tc.margin_top is None  # unchanged

def test_theme_config_apply_frame_bar_bool():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig(frame_bar=True)
    tc.apply("frame-bar", "false")
    assert tc.frame_bar is False

def test_theme_config_apply_frame_bar_title():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("frame-bar-title", "My Terminal")
    assert tc.frame_bar_title == "My Terminal"

def test_theme_config_apply_nullable_none():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig(background="ff0000")
    tc.apply("background", "none")
    assert tc.background is None

def test_theme_config_apply_unknown_key_ignored():
    from scriptcast.config import ThemeConfig
    tc = ThemeConfig()
    tc.apply("nonexistent-key", "value")  # must not raise


def test_scriptcast_config_has_theme():
    from scriptcast.config import ScriptcastConfig, ThemeConfig
    sc = ScriptcastConfig()
    assert isinstance(sc.theme, ThemeConfig)

def test_scriptcast_config_theme_defaults():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    assert sc.theme.frame is True
    assert sc.theme.background == "1e1b4b,0d3b66"

def test_scriptcast_config_apply_theme_key():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-radius", "20"])
    assert sc.theme.radius == 20

def test_scriptcast_config_apply_theme_background():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-background", "ff0000,0000ff"])
    assert sc.theme.background == "ff0000,0000ff"

def test_scriptcast_config_apply_theme_bool():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-frame", "false"])
    assert sc.theme.frame is False

def test_scriptcast_config_apply_theme_margin():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["theme-margin", "32 32 64"])
    assert sc.theme.margin_bottom == 64

def test_scriptcast_config_apply_terminal_theme_not_delegated():
    """terminal-theme must NOT be routed to ThemeConfig; stays on ScriptcastConfig."""
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc.apply("set", ["terminal-theme", "light"])
    assert sc.terminal_theme == "light"

def test_copy_deep_copies_theme():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc2 = sc.copy()
    sc2.theme.radius = 999
    assert sc.theme.radius == 12  # unchanged

def test_copy_is_still_independent_for_scalar():
    from scriptcast.config import ScriptcastConfig
    sc = ScriptcastConfig()
    sc2 = sc.copy()
    sc2.type_speed = 999
    assert sc.type_speed == 40

def test_cr_delay_default():
    c = ScriptcastConfig()
    assert c.cr_delay == 0

def test_apply_set_cr_delay():
    c = ScriptcastConfig()
    c.apply("set", ["cr-delay", "80"])
    assert c.cr_delay == 80


# ── extract_config_prefix ─────────────────────────────────────────────────

def test_extract_config_prefix_empty():
    from scriptcast.config import extract_config_prefix
    assert extract_config_prefix("") == ""


def test_extract_config_prefix_blank_and_comments():
    from scriptcast.config import extract_config_prefix
    src = "# comment\n\n# another\n"
    assert extract_config_prefix(src) == src


def test_extract_config_prefix_var_assignment():
    from scriptcast.config import extract_config_prefix
    src = "GREEN='\\033[32m'\nRESET='\\033[0m'\n"
    assert extract_config_prefix(src) == src


def test_extract_config_prefix_sc_set():
    from scriptcast.config import extract_config_prefix
    src = ": SC set width 80\n: SC set height 24\n"
    assert extract_config_prefix(src) == src


def test_extract_config_prefix_stops_at_scene():
    from scriptcast.config import extract_config_prefix
    src = ": SC set width 80\n: SC scene main\necho hi\n"
    assert extract_config_prefix(src) == ": SC set width 80\n"


def test_extract_config_prefix_stops_at_real_command():
    from scriptcast.config import extract_config_prefix
    src = ": SC set width 80\necho hello\n"
    assert extract_config_prefix(src) == ": SC set width 80\n"


def test_extract_config_prefix_stops_at_filter():
    from scriptcast.config import extract_config_prefix
    src = ": SC set width 80\n: SC filter foo\necho hi\n"
    assert extract_config_prefix(src) == ": SC set width 80\n"


def test_extract_config_prefix_stops_at_type():
    from scriptcast.config import extract_config_prefix
    src = ": SC set width 80\n: SC type hello\n"
    assert extract_config_prefix(src) == ": SC set width 80\n"


def test_extract_config_prefix_record_pause_block_collected():
    from scriptcast.config import extract_config_prefix
    src = (
        ": SC record pause\n"
        "GREEN='\\033[32m'\n"
        ": SC record resume\n"
        ": SC set prompt \"${GREEN} > \"\n"
    )
    assert extract_config_prefix(src) == src


def test_extract_config_prefix_record_pause_real_cmd_inside_collected():
    """Commands inside a record pause block are still collected (explicitly hidden)."""
    from scriptcast.config import extract_config_prefix
    src = (
        ": SC record pause\n"
        "some_real_cmd arg\n"
        ": SC record resume\n"
        ": SC set width 80\n"
    )
    assert extract_config_prefix(src) == src


def test_extract_config_prefix_stops_after_record_resume_at_scene():
    from scriptcast.config import extract_config_prefix
    src = (
        ": SC record pause\n"
        "GREEN='\\033[32m'\n"
        ": SC record resume\n"
        ": SC scene main\n"
        "echo hi\n"
    )
    expected = (
        ": SC record pause\n"
        "GREEN='\\033[32m'\n"
        ": SC record resume\n"
    )
    assert extract_config_prefix(src) == expected


def test_extract_config_prefix_custom_directive_prefix():
    from scriptcast.config import extract_config_prefix
    src = ": DEMO set width 80\n: DEMO scene main\necho hi\n"
    assert extract_config_prefix(src, directive_prefix="DEMO") == ": DEMO set width 80\n"


def test_extract_config_prefix_export_var_assignment():
    from scriptcast.config import extract_config_prefix
    src = "export FOO=bar\n: SC scene main\n"
    assert extract_config_prefix(src, directive_prefix="SC") == "export FOO=bar\n"
