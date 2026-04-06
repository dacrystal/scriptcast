# tests/test_generator.py
import json

from scriptcast.generator import generate_from_sc, generate_from_sc_text


def _make_sc(*events, width=80, height=24):
    header = {"version": 1, "width": width, "height": height,
              "directive-prefix": "SC", "pipeline-version": 3}
    lines = [json.dumps(header)]
    ts = 1.0
    for typ, text in events:
        lines.append(json.dumps([ts, typ, text]))
        ts += 0.001
    return "\n".join(lines) + "\n"


def _zero_sc(*events):
    zero = [
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set input_wait 0"),
    ]
    return _make_sc(*zero, *events)


def _cast(path):
    lines = [ln for ln in path.read_text().strip().splitlines() if ln]
    return json.loads(lines[0]), [json.loads(ln) for ln in lines[1:]]


def test_cast_header_version(tmp_path):
    paths = generate_from_sc_text(_zero_sc(), tmp_path)
    header, _ = _cast(paths[0])
    assert header["version"] == 2


def test_cast_header_dimensions(tmp_path):
    sc = _make_sc(width=120, height=30)
    paths = generate_from_sc_text(sc, tmp_path)
    header, _ = _cast(paths[0])
    assert header["width"] == 120
    assert header["height"] == 30


def test_cmd_event_typed_as_output(tmp_path):
    paths = generate_from_sc_text(_zero_sc(("cmd", "echo hi")), tmp_path)
    _, cast = _cast(paths[0])
    assert "echo hi" in "".join(e[2] for e in cast)


def test_output_event_in_cast(tmp_path):
    paths = generate_from_sc_text(_zero_sc(("cmd", "echo hi"), ("out", "hi")), tmp_path)
    _, cast = _cast(paths[0])
    assert "hi" in "".join(e[2] for e in cast)


def test_exit_wait_at_scene_end(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set exit_wait 400"),
        ("cmd", "echo x"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.4


def test_expect_input_advances_cursor(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set input_wait 300"),
        ("dir", "expect-input secret"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.3


def test_sleep_directive_advances_cursor(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("cmd", "a"),
        ("dir", "sleep 500"),
        ("cmd", "b"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.5


def test_scene_split_mode(tmp_path):
    sc = _zero_sc(
        ("dir", "scene intro"),
        ("cmd", "echo a"),
        ("dir", "scene outro"),
        ("cmd", "echo b"),
    )
    paths = generate_from_sc_text(sc, tmp_path, split_scenes=True)
    assert {p.stem for p in paths} == {"intro", "outro"}


def test_single_cast_default(tmp_path):
    sc = _zero_sc(
        ("dir", "scene first"),
        ("cmd", "echo a"),
        ("dir", "scene second"),
        ("cmd", "echo b"),
    )
    paths = generate_from_sc_text(sc, tmp_path, output_stem="demo")
    assert len(paths) == 1
    assert paths[0].name == "demo.cast"


def test_single_cast_timestamps_continuous(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set exit_wait 200"),
        ("dir", "scene a"),
        ("cmd", "x"),
        ("dir", "scene b"),
        ("cmd", "y"),
    )
    paths = generate_from_sc_text(sc, tmp_path, output_stem="out")
    _, cast = _cast(paths[0])
    times = [e[0] for e in cast]
    assert times == sorted(times)
    assert max(times) > 0.2


def test_generate_from_sc_reads_file(tmp_path):
    sc = _zero_sc(("cmd", "echo hello"))
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc)
    out = tmp_path / "out"
    out.mkdir()
    paths = generate_from_sc(sc_file, out)
    _, cast = _cast(paths[0])
    assert "echo hello" in "".join(e[2] for e in cast)


def test_word_speed_adds_pause_between_words(tmp_path):
    # "echo hello world" has 2 spaces → 2 word pauses of 200ms each = 400ms
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set word_speed 200"),
        ("cmd", "echo hello world"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.4


def test_word_speed_none_mirrors_type_speed(tmp_path):
    # word_speed=None → word pause = type_speed (100ms here); "a b" has 1 space
    # chars: 'a' at 0.1, ' ' at 0.2 + word_pause 0.1 = 0.3, 'b' at 0.4, prompt/sentinel at 0.5
    sc = _make_sc(
        ("dir", "set type_speed 100"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("cmd", "a b"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.5


def test_word_speed_applies_to_expect_input(tmp_path):
    # "foo bar" has 1 space → 1 word pause of 300ms
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set input_wait 0"),
        ("dir", "set word_speed 300"),
        ("dir", "expect-input foo bar"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.3


def test_quoted_prompt_in_pre_scene_set(tmp_path):
    # bash traces `"$ "` as `'$ '`; shlex.split must handle shell quoting in the
    # pre-scene directive loop so the cast shows "$ " not "'$"
    sc = _make_sc(
        ("dir", "set prompt '$ '"),
        ("dir", "scene main"),
        ("cmd", "echo hi"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    prompt_events = [e for e in cast if e[2] == "$ "]
    assert prompt_events, f"expected '$ ' prompt in cast, got: {cast}"


def test_build_config_from_sc_text_reads_header():
    from scriptcast.generator import build_config_from_sc_text
    import json
    header = json.dumps({"version": 1, "shell": "bash", "width": 80, "height": 24,
                         "directive-prefix": "SC"})
    sc = header + "\n"
    cfg = build_config_from_sc_text(sc)
    assert cfg.width == 80
    assert cfg.height == 24
    assert cfg.directive_prefix == "SC"


def test_build_config_from_sc_text_applies_pre_scene_set():
    from scriptcast.generator import build_config_from_sc_text
    import json
    header = json.dumps({"version": 1, "width": 100, "height": 28, "directive-prefix": "SC"})
    events = [
        json.dumps([0.0, "dir", "set type_speed 20"]),
        json.dumps([0.1, "dir", "set theme-radius 16"]),
        json.dumps([0.2, "dir", "scene main"]),
        json.dumps([0.3, "cmd", "echo hello"]),
    ]
    sc = header + "\n" + "\n".join(events)
    cfg = build_config_from_sc_text(sc)
    assert cfg.type_speed == 20
    assert cfg.theme.radius == 16


def test_build_config_from_sc_text_stops_at_scene():
    from scriptcast.generator import build_config_from_sc_text
    import json
    header = json.dumps({"version": 1, "width": 100, "height": 28, "directive-prefix": "SC"})
    events = [
        json.dumps([0.0, "dir", "scene main"]),
        json.dumps([0.1, "dir", "set type_speed 99"]),
    ]
    sc = header + "\n" + "\n".join(events)
    cfg = build_config_from_sc_text(sc)
    assert cfg.type_speed == 40  # default, not overridden after scene


def test_build_config_from_sc_text_empty_returns_defaults():
    from scriptcast.generator import build_config_from_sc_text
    cfg = build_config_from_sc_text("")
    assert cfg.type_speed == 40
    assert cfg.theme.frame is True


# --- build_config_from_sc_text: base parameter ---

def test_build_config_from_sc_text_base_provides_defaults():
    from scriptcast.config import ScriptcastConfig
    from scriptcast.generator import build_config_from_sc_text
    import json
    base = ScriptcastConfig(prompt="THEME_PROMPT")
    base.theme.radius = 99
    header = json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"})
    sc = header + "\n"
    cfg = build_config_from_sc_text(sc, base=base)
    assert cfg.prompt == "THEME_PROMPT"
    assert cfg.theme.radius == 99


def test_build_config_from_sc_text_sc_overrides_base():
    from scriptcast.config import ScriptcastConfig
    from scriptcast.generator import build_config_from_sc_text
    import json
    base = ScriptcastConfig(prompt="THEME_PROMPT")
    header = json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"})
    events = [json.dumps([0.0, "dir", "set prompt SC_PROMPT"])]
    sc = header + "\n" + "\n".join(events)
    cfg = build_config_from_sc_text(sc, base=base)
    assert cfg.prompt == "SC_PROMPT"


def test_build_config_from_sc_text_base_none_is_default():
    from scriptcast.generator import build_config_from_sc_text
    import json
    header = json.dumps({"version": 1, "width": 80, "height": 24, "directive-prefix": "SC"})
    sc = header + "\n"
    cfg = build_config_from_sc_text(sc, base=None)
    assert cfg.prompt == "$ "


# --- generate_from_sc_text: base parameter ---

def test_generate_from_sc_text_base_prompt_in_cast(tmp_path):
    from scriptcast.config import ScriptcastConfig
    base = ScriptcastConfig(prompt="THEME>")
    sc = _zero_sc(
        ("dir", "scene main"),
        ("cmd", "echo hi"),
    )
    paths = generate_from_sc_text(sc, tmp_path, base=base)
    _, cast = _cast(paths[0])
    prompt_text = "".join(e[2] for e in cast)
    assert "THEME>" in prompt_text, f"Expected 'THEME>' in cast output, got: {prompt_text!r}"


def test_generate_from_sc_text_sc_prompt_overrides_base(tmp_path):
    from scriptcast.config import ScriptcastConfig
    base = ScriptcastConfig(prompt="THEME>")
    sc = _zero_sc(
        ("dir", "set prompt SCRIPT>"),
        ("dir", "scene main"),
        ("cmd", "echo hi"),
    )
    paths = generate_from_sc_text(sc, tmp_path, base=base)
    _, cast = _cast(paths[0])
    prompt_text = "".join(e[2] for e in cast)
    assert "SCRIPT>" in prompt_text, f"Expected 'SCRIPT>' prompt override in cast"
    assert "THEME>" not in prompt_text, f"Theme prompt should be overridden"


def test_generate_from_sc_text_base_type_speed(tmp_path):
    from scriptcast.config import ScriptcastConfig
    # base sets type_speed=200; sc has no override; "ab" = 2 chars → 400ms
    base = ScriptcastConfig(cmd_wait=0, exit_wait=0, enter_wait=0, type_speed=200)
    sc = _make_sc(("cmd", "ab"))
    paths = generate_from_sc_text(sc, tmp_path, base=base)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.4


def test_generate_from_sc_reads_file_with_base(tmp_path):
    from scriptcast.config import ScriptcastConfig
    base = ScriptcastConfig(prompt="FILE>")
    sc = _zero_sc(("dir", "scene main"), ("cmd", "echo hi"))
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc)
    out = tmp_path / "out"
    out.mkdir()
    paths = generate_from_sc(sc_file, out, base=base)
    _, cast = _cast(paths[0])
    prompt_text = "".join(e[2] for e in cast)
    assert "FILE>" in prompt_text


def test_expect_input_directive_advances_cursor(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set input_wait 300"),
        ("dir", "expect-input secret"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.3


def test_expect_input_directive_emits_chars(tmp_path):
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set input_wait 0"),
        ("dir", "expect-input hi"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    all_text = "".join(e[2] for e in cast)
    assert "h" in all_text
    assert "i" in all_text


def test_out_event_no_suffix_added(tmp_path):
    # Generator must NOT append \r\n — text is emitted verbatim
    paths = generate_from_sc_text(_zero_sc(("out", "hello")), tmp_path)
    _, cast = _cast(paths[0])
    # There must be a cast event with exactly "hello" (no \r\n appended)
    assert any(e[2] == "hello" for e in cast), \
        "expected 'hello' verbatim; old code would emit 'hello\\r\\n'"


def test_cr_delay_splits_bare_cr(tmp_path):
    # out event with bare \r: with cr_delay=80, two cast events emitted at different times
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set cr_delay 80"),
        ("out", "Loading\rDone\n"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    all_text = "".join(e[2] for e in cast)
    assert "Loading" in all_text
    assert "\rDone" in all_text
    # The \r split creates two events at different timestamps
    loading_events = [e for e in cast if "Loading" in e[2] and "\r" not in e[2]]
    done_events = [e for e in cast if "\rDone" in e[2]]
    assert loading_events and done_events
    assert done_events[0][0] >= loading_events[0][0] + 0.079


def test_crlf_not_split_by_cr_delay(tmp_path):
    # \r\n is a line ending — cr_delay must NOT split it
    sc = _make_sc(
        ("dir", "set type_speed 0"),
        ("dir", "set cmd_wait 0"),
        ("dir", "set exit_wait 0"),
        ("dir", "set enter_wait 0"),
        ("dir", "set cr_delay 80"),
        ("out", "hello\r\n"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    # hello\r\n should appear as a single event (no split)
    hello_events = [e for e in cast if "hello" in e[2]]
    assert len(hello_events) == 1
    assert hello_events[0][2] == "hello\r\n"
