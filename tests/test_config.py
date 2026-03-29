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
    assert c.theme == "dark"
    assert c.prompt == "$ "
    assert c.directive_prefix == "SC"
    assert c.trace_prefix == "+"
    assert c.show_title is False
    assert c.split_scenes is False

def test_apply_set_int():
    c = ScriptcastConfig()
    c.apply("set", ["type_speed", "60"])
    assert c.type_speed == 60

def test_apply_set_str():
    c = ScriptcastConfig()
    c.apply("set", ["theme", "light"])
    assert c.theme == "light"

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
