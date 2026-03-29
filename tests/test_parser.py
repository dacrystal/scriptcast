# tests/test_parser.py
import pytest
from scriptcast.parser import parse_sc_text
from scriptcast.model import SceneStart, CommandTrace, OutputLine, Directive, PauseBlock, InputLine

SIMPLE = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + : SC set type_speed 40
1.1 + : SC scene Intro
1.2 + echo hello
1.3 hello
"""

def test_scene_start_parsed():
    _, events = parse_sc_text(SIMPLE)
    assert SceneStart(name="Intro") in events

def test_command_trace_parsed():
    _, events = parse_sc_text(SIMPLE)
    assert CommandTrace(text="echo hello") in events

def test_output_line_parsed():
    _, events = parse_sc_text(SIMPLE)
    assert OutputLine(text="hello") in events

def test_global_config_applied():
    config, _ = parse_sc_text(SIMPLE)
    assert config.type_speed == 40

def test_sc_directive_not_in_events_as_command_trace():
    _, events = parse_sc_text(SIMPLE)
    for e in events:
        if isinstance(e, CommandTrace):
            assert not e.text.startswith(": SC")

def test_no_scene_defaults_to_main():
    sc = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + echo hello
1.1 hello
"""
    _, events = parse_sc_text(sc)
    assert events[0] == SceneStart(name="main")

def test_pause_block_wraps_events():
    sc = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + : SC scene Test
1.1 + : SC record pause
1.2 + PS1=>
1.3 + : SC record resume
1.4 + echo after
1.5 after
"""
    _, events = parse_sc_text(sc)
    non_scene = [e for e in events if not isinstance(e, SceneStart)]
    assert isinstance(non_scene[0], PauseBlock)
    assert isinstance(non_scene[1], CommandTrace)
    assert non_scene[1].text == "echo after"

def test_unknown_directive_preserved_as_directive():
    sc = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + : SC scene Test
1.1 + : SC unknownfuture foo bar
"""
    _, events = parse_sc_text(sc)
    directives = [e for e in events if isinstance(e, Directive)]
    assert any(d.name == "unknownfuture" for d in directives)

def test_pause_without_resume_warns():
    sc = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + : SC scene Test
1.1 + : SC record pause
1.2 + echo inside
"""
    with pytest.warns(UserWarning, match="pause without"):
        parse_sc_text(sc)

def test_resume_without_pause_warns():
    sc = """\
#shell=bash
#trace-prefix=+
#directive-prefix=SC
1.0 + : SC scene Test
1.1 + : SC record resume
1.2 + echo after
"""
    with pytest.warns(UserWarning, match="resume without"):
        parse_sc_text(sc)

def test_sc_mark_input_parsed_as_input_line():
    text = (
        "#shell=bash\n"
        "#trace-prefix=+\n"
        "#directive-prefix=SC\n"
        "1.000 : SC mark input\n"
    )
    _, events = parse_sc_text(text)
    input_lines = [e for e in events if isinstance(e, InputLine)]
    assert len(input_lines) == 1

def test_sc_mark_input_not_emitted_as_output_line():
    text = (
        "#shell=bash\n"
        "#trace-prefix=+\n"
        "#directive-prefix=SC\n"
        "1.000 : SC mark input\n"
    )
    _, events = parse_sc_text(text)
    assert not any(isinstance(e, OutputLine) for e in events)
