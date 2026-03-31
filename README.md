# scriptcast

[![Standard Readme](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg)](https://github.com/RichardLitt/standard-readme)
[![PyPI version](https://img.shields.io/pypi/v/scriptcast.svg)](https://pypi.org/project/scriptcast/)
[![Tests](https://github.com/dacrystal/scriptcast/actions/workflows/tests.yml/badge.svg)](https://github.com/dacrystal/scriptcast/actions)

Generate terminal demos (asciinema casts & GIFs) from annotated shell scripts.

scriptcast turns a shell script into a reproducible, polished terminal demo — with
typing animations, multiple scenes, mocked commands, interactive sessions, output
filtering, and more.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Script Syntax](#script-syntax)
- [Contributing](#contributing)
- [License](#license)

## Background

Terminal demos are hard to reproduce. Screen recordings drift, manual re-runs produce
different output, and polishing timing or hiding sensitive paths requires video editing.

scriptcast treats demos as code. You write a shell script annotated with `SC`
directives — controlling scenes, typing speed, mocked commands, interactive expect
sessions, and output filters — then run a two-stage pipeline:

1. **Record** — the script executes with shell tracing enabled; raw output is captured
   and written to a JSONL `.sc` file containing timestamped `cmd`, `output`, `input`,
   and `directive` events.
2. **Generate** — the `.sc` file is read by a streaming renderer that synthesises a
   polished asciinema `.cast` file with typing animations and timing.

The `.sc` file is plain text, version-controllable, and diffable. Re-generating a cast
from an existing `.sc` is instant.

## Install

```bash
pip install scriptcast
```

Requires Python 3.10+. For GIF output, install [agg](https://github.com/asciinema/agg).

### From source

```bash
git clone https://github.com/dacrystal/scriptcast.git
cd scriptcast
pip install -e .
```

## Usage

```bash
# End-to-end: record script and generate .cast file(s)
scriptcast demo.sh

# Stage 1 — record to .sc file
scriptcast record demo.sh

# Stage 2 — generate .cast file(s) from a recorded .sc
scriptcast generate demo.sc

# Generate GIFs from a .sc file (requires agg)
scriptcast gif demo.sc
```

Key flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir PATH` | same dir as input | Where to write output files |
| `--directive-prefix PREFIX` | `SC` | Directive prefix used in scripts |
| `--trace-prefix CHAR` | `+` | PS4/xtrace prefix |
| `--title` / `--no-title` | off | Show scene name at the start of each cast |
| `--shell PATH` | `$SHELL` | Shell used for recording |

## Script Syntax

Scripts are valid shell scripts. `SC` directives are embedded as shell no-ops
(`: SC ...`) so they execute harmlessly but appear in the xtrace output for the
recorder to process.

```sh
#!/usr/bin/env scriptcast

# Global config — applied before any scene
: SC set type_speed 40
: SC set width 80
: SC set height 24

# ── Scene: intro ──────────────────────────────
: SC scene intro

echo "Hello from scriptcast"

# ── Scene: mock ───────────────────────────────
: SC scene mock

: SC mock deploy <<'EOF'
Deploying to production...
Build: OK
Tests: OK
Deploy: OK
EOF

deploy

# ── Scene: expect ─────────────────────────────
: SC scene expect

: SC expect ./my-app <<'EOF'
expect "Password:"
send "secret\r"
expect "prompt>"
send "quit\r"
expect eof
EOF

# ── Scene: filter ─────────────────────────────
: SC scene filter

: SC filter sed 's#/home/user/projects#<project>#g'

pwd

# ── Scene: setup (not recorded) ───────────────
: SC scene setup

: SC record pause
DB_URL="postgres://localhost/mydb"
: SC record resume

echo "Connecting to $DB_URL"
```

### Recorder directives

These are consumed during recording and never appear in the `.sc` file.

| Directive | Description |
|-----------|-------------|
| `SC mock <cmd> <<'EOF'` ... `EOF` | Mock `<cmd>` so it prints fixed output during recording |
| `SC expect <cmd> <<'EOF'` ... `EOF` | Run an interactive session via [expect(1)](https://core.tcl-lang.org/expect/index) |
| `SC record pause` | Stop capturing output (commands still execute) |
| `SC record resume` | Resume capturing |
| `SC filter sed '<expr>'` | Replace the current output filter with a sed expression |
| `SC filter-add sed '<expr>'` | Append a sed expression to the current filter chain |

#### `SC expect` syntax

The heredoc body is a standard expect script. scriptcast preprocesses it to capture
typed input and clean up spawn noise. Inputs sent with `send` are recorded as `input`
events; silent inputs (e.g. passwords read with `read -rs`) produce silent animations.

```sh
: SC expect ./fake-db <<'EOF'
expect "Password:"
send "secret\r"
expect "mysql>"
send "show databases;\r"
expect eof
EOF
```

### Generator directives

These are stored in the `.sc` file and interpreted during cast generation.

| Directive | Description |
|-----------|-------------|
| `SC scene <name>` | Start a new scene |
| `SC set <key> <value>` | Set a timing or display config key |
| `SC sleep <ms>` | Pause for N milliseconds |

### Config keys (`SC set`)

| Key | Default | Description |
|-----|---------|-------------|
| `type_speed` | `40` | ms per character when typing commands |
| `cmd_wait` | `80` | ms after a command is typed, before output |
| `input_wait` | `80` | ms to pause before typing interactive input |
| `enter_wait` | `80` | ms at the start of each scene, after clearing |
| `exit_wait` | `120` | ms after the last output line of a scene |
| `width` | `100` | Terminal width (columns) |
| `height` | `28` | Terminal height (rows) |
| `prompt` | `$ ` | Prompt string shown before commands |
| `theme` | `dark` | Terminal colour theme |

## Contributing

Issues and pull requests are welcome at
[github.com/dacrystal/scriptcast](https://github.com/dacrystal/scriptcast/issues).

Before opening a PR, ensure:
- All tests pass: `uv run pytest`
- New behaviour is covered by tests

## License

MIT © dacrystal
