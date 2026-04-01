# tests/test_generator.py
import json

from scriptcast.generator import generate_from_sc, generate_from_sc_text


def _make_sc(*events, width=80, height=24):
    header = {"version": 1, "width": width, "height": height, "directive-prefix": "SC"}
    lines = [json.dumps(header)]
    ts = 1.0
    for typ, text in events:
        lines.append(json.dumps([ts, typ, text]))
        ts += 0.001
    return "\n".join(lines) + "\n"


def _zero_sc(*events):
    zero = [
        ("directive", "set type_speed 0"),
        ("directive", "set cmd_wait 0"),
        ("directive", "set exit_wait 0"),
        ("directive", "set enter_wait 0"),
        ("directive", "set input_wait 0"),
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
    paths = generate_from_sc_text(_zero_sc(("cmd", "echo hi"), ("output", "hi")), tmp_path)
    _, cast = _cast(paths[0])
    assert "hi" in "".join(e[2] for e in cast)


def test_exit_wait_at_scene_end(tmp_path):
    sc = _make_sc(
        ("directive", "set type_speed 0"),
        ("directive", "set cmd_wait 0"),
        ("directive", "set enter_wait 0"),
        ("directive", "set exit_wait 400"),
        ("cmd", "echo x"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.4


def test_input_event_advances_cursor(tmp_path):
    sc = _make_sc(
        ("directive", "set type_speed 0"),
        ("directive", "set cmd_wait 0"),
        ("directive", "set exit_wait 0"),
        ("directive", "set enter_wait 0"),
        ("directive", "set input_wait 300"),
        ("input", "secret"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.3


def test_sleep_directive_advances_cursor(tmp_path):
    sc = _make_sc(
        ("directive", "set type_speed 0"),
        ("directive", "set cmd_wait 0"),
        ("directive", "set exit_wait 0"),
        ("directive", "set enter_wait 0"),
        ("cmd", "a"),
        ("directive", "sleep 500"),
        ("cmd", "b"),
    )
    paths = generate_from_sc_text(sc, tmp_path)
    _, cast = _cast(paths[0])
    assert max(e[0] for e in cast) >= 0.5


def test_scene_split_mode(tmp_path):
    sc = _zero_sc(
        ("directive", "scene intro"),
        ("cmd", "echo a"),
        ("directive", "scene outro"),
        ("cmd", "echo b"),
    )
    paths = generate_from_sc_text(sc, tmp_path, split_scenes=True)
    assert {p.stem for p in paths} == {"intro", "outro"}


def test_single_cast_default(tmp_path):
    sc = _zero_sc(
        ("directive", "scene first"),
        ("cmd", "echo a"),
        ("directive", "scene second"),
        ("cmd", "echo b"),
    )
    paths = generate_from_sc_text(sc, tmp_path, output_stem="demo")
    assert len(paths) == 1
    assert paths[0].name == "demo.cast"


def test_single_cast_timestamps_continuous(tmp_path):
    sc = _make_sc(
        ("directive", "set type_speed 0"),
        ("directive", "set cmd_wait 0"),
        ("directive", "set enter_wait 0"),
        ("directive", "set exit_wait 200"),
        ("directive", "scene a"),
        ("cmd", "x"),
        ("directive", "scene b"),
        ("cmd", "y"),
    )
    paths = generate_from_sc_text(sc, tmp_path, output_stem="out")
    _, cast = _cast(paths[0])
    times = [e[0] for e in cast]
    assert times == sorted(times)
    assert max(times) > 0.2


def test_show_title_emits_scene_name(tmp_path):
    sc = _zero_sc(("directive", "scene MyScene"), ("cmd", "echo x"))
    paths = generate_from_sc_text(sc, tmp_path, show_title=True)
    _, cast = _cast(paths[0])
    assert "MyScene" in "".join(e[2] for e in cast)


def test_generate_from_sc_reads_file(tmp_path):
    sc = _zero_sc(("cmd", "echo hello"))
    sc_file = tmp_path / "demo.sc"
    sc_file.write_text(sc)
    out = tmp_path / "out"
    out.mkdir()
    paths = generate_from_sc(sc_file, out)
    _, cast = _cast(paths[0])
    assert "echo hello" in "".join(e[2] for e in cast)
