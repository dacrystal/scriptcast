# tests/test_model.py
from scriptcast.model import SceneStart, CommandTrace, OutputLine, Directive, PauseBlock, InputLine, ScriptEvent
from typing import get_args

def test_scene_start_defaults():
    s = SceneStart(name="Intro")
    assert s.name == "Intro"

def test_command_trace():
    assert CommandTrace(text="echo hello").text == "echo hello"

def test_directive():
    d = Directive(name="set", args=["type_speed", "40"])
    assert d.name == "set"
    assert d.args == ["type_speed", "40"]

def test_pause_block_contains_events():
    inner = [CommandTrace(text="PS1=>")]
    p = PauseBlock(events=inner)
    assert p.events[0].text == "PS1=>"

def test_input_line_default_text():
    e = InputLine()
    assert e.text == ""

def test_input_line_in_script_event_union():
    assert InputLine in get_args(ScriptEvent)
