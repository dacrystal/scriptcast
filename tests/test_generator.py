# tests/test_generator.py
import json
import pytest
from scriptcast.config import ScriptcastConfig
from scriptcast.generator import generate_scene, generate_all_scenes
from scriptcast.model import (
    CommandTrace, Directive, InputLine, OutputLine, PauseBlock, SceneStart
)

def zero_config() -> ScriptcastConfig:
    """Config with zero delays for predictable test output."""
    c = ScriptcastConfig()
    c.type_speed = 0
    c.cmd_wait = 0
    c.exit_wait = 0
    c.enter_wait = 0
    c.input_wait = 0
    return c


def parse_cast(content: str) -> tuple[dict, list]:
    lines = [l for l in content.strip().splitlines() if l]
    header = json.loads(lines[0])
    events = [json.loads(l) for l in lines[1:]]
    return header, events


def test_cast_header_version():
    header, _ = parse_cast(generate_scene([], zero_config(), "test"))
    assert header["version"] == 2


def test_cast_header_dimensions():
    c = zero_config()
    c.width = 120
    c.height = 30
    header, _ = parse_cast(generate_scene([], c, "test"))
    assert header["width"] == 120
    assert header["height"] == 30


def test_command_typed_as_output():
    events = [CommandTrace(text="echo hi")]
    _, cast_events = parse_cast(generate_scene(events, zero_config(), "test"))
    all_text = "".join(e[2] for e in cast_events if e[1] == "o")
    assert "echo hi" in all_text


def test_output_line_in_cast():
    events = [CommandTrace(text="echo hi"), OutputLine(text="hi")]
    _, cast_events = parse_cast(generate_scene(events, zero_config(), "test"))
    all_text = "".join(e[2] for e in cast_events if e[1] == "o")
    assert "hi" in all_text


def test_pause_block_not_in_cast():
    events = [PauseBlock(events=[CommandTrace(text="SECRET")])]
    _, cast_events = parse_cast(generate_scene(events, zero_config(), "test"))
    all_text = "".join(e[2] for e in cast_events if e[1] == "o")
    assert "SECRET" not in all_text


def test_sc_sleep_advances_cursor():
    c = ScriptcastConfig()
    c.type_speed = 0
    c.cmd_wait = 0
    c.exit_wait = 0
    c.enter_wait = 0
    events = [
        CommandTrace(text="a"),
        Directive(name="sleep", args=["500"]),
        CommandTrace(text="b"),
    ]
    _, cast_events = parse_cast(generate_scene(events, c, "test"))
    times = [e[0] for e in cast_events if e[1] == "o"]
    # The second command should appear at t >= 0.5 due to sleep
    # Find the index of "b" in output and check its time
    # (with zero type_speed, "b" prompt char appears right after sleep)
    assert max(times) >= 0.5


def test_filter_applied_to_output():
    events = [
        Directive(name="filter", args=["sed", "s#/home/user#~#g"]),
        CommandTrace(text="pwd"),
        OutputLine(text="/home/user/project"),
    ]
    _, cast_events = parse_cast(generate_scene(events, zero_config(), "test"))
    all_text = "".join(e[2] for e in cast_events if e[1] == "o")
    assert "~/project" in all_text
    assert "/home/user" not in all_text


def test_show_title_emits_scene_name():
    c = zero_config()
    c.show_title = True
    _, cast_events = parse_cast(generate_scene([], c, "MyScene"))
    all_text = "".join(e[2] for e in cast_events if e[1] == "o")
    assert "MyScene" in all_text


def test_input_line_advances_cursor_by_input_wait():
    c = ScriptcastConfig()
    c.type_speed = 0
    c.cmd_wait = 0
    c.exit_wait = 0
    c.enter_wait = 0
    c.input_wait = 300
    events = [InputLine()]
    _, cast_events = parse_cast(generate_scene(events, c, "test"))
    # Only non-zero time should be from input_wait (0.3s)
    times = [e[0] for e in cast_events if e[1] == "o"]
    assert max(times) >= 0.3

def test_enter_wait_applied_at_scene_start():
    c = ScriptcastConfig()
    c.type_speed = 0
    c.cmd_wait = 0
    c.exit_wait = 0
    c.enter_wait = 500
    # The clear screen event is at t=0; first command should be at t>=0.5
    events = [CommandTrace(text="x")]
    _, cast_events = parse_cast(generate_scene(events, c, "test"))
    output_texts = [(e[0], e[2]) for e in cast_events if e[1] == "o"]
    # Find the prompt character (not the clear escape)
    prompt_times = [t for t, txt in output_texts if txt == "$ "]
    assert prompt_times[0] >= 0.5

def test_exit_wait_always_applied_at_scene_end():
    """exit_wait applies at scene end even if last event was a CommandTrace."""
    c = ScriptcastConfig()
    c.type_speed = 0
    c.cmd_wait = 0
    c.exit_wait = 400
    c.enter_wait = 0
    events = [CommandTrace(text="x")]  # last event is not OutputLine
    _, cast_events = parse_cast(generate_scene(events, c, "test"))
    times = [e[0] for e in cast_events if e[1] == "o"]
    assert max(times) >= 0.4


def test_generate_all_scenes_split_mode_creates_one_file_per_scene(tmp_path):
    c = zero_config()
    c.split_scenes = True
    events = [
        SceneStart(name="first"),
        CommandTrace(text="echo a"),
        OutputLine(text="a"),
        SceneStart(name="second"),
        CommandTrace(text="echo b"),
        OutputLine(text="b"),
    ]
    paths = generate_all_scenes(events, c, tmp_path)
    names = {p.name for p in paths}
    assert "first.cast" in names
    assert "second.cast" in names


def test_generate_all_scenes_single_cast_default(tmp_path):
    events = [
        SceneStart(name="first"),
        CommandTrace(text="echo a"),
        SceneStart(name="second"),
        CommandTrace(text="echo b"),
    ]
    paths = generate_all_scenes(events, zero_config(), tmp_path, output_stem="demo")
    assert len(paths) == 1
    assert paths[0].name == "demo.cast"
    content = paths[0].read_text()
    header = json.loads(content.splitlines()[0])
    assert header["version"] == 2


def test_single_cast_timestamps_are_continuous(tmp_path):
    """Scene N+1 timestamps continue from where scene N ended."""
    c = zero_config()
    c.exit_wait = 200  # 0.2s at end of each scene
    events = [
        SceneStart(name="a"),
        CommandTrace(text="x"),
        SceneStart(name="b"),
        CommandTrace(text="y"),
    ]
    paths = generate_all_scenes(events, c, tmp_path, output_stem="out")
    lines = paths[0].read_text().splitlines()
    cast_events = [json.loads(l) for l in lines[1:]]
    times = [e[0] for e in cast_events if e[1] == "o"]
    # All timestamps should be monotonically increasing
    assert times == sorted(times)
    # Scene B starts after scene A's exit_wait
    assert max(times) > 0.2
