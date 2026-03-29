# scriptcast

[![Standard Readme](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg)](https://github.com/RichardLitt/standard-readme)
[![PyPI version](https://img.shields.io/pypi/v/scriptcast.svg)](https://pypi.org/project/scriptcast/)
[![Tests](https://github.com/dacrystal/scriptcast/actions/workflows/tests.yml/badge.svg)](https://github.com/dacrystal/scriptcast/actions)

Generate terminal demos (asciinema casts & GIFs) from simple shell-like scripts.

scriptcast lets you describe terminal interactions as a script — then turns them into
reproducible, polished demos with typing effects, multiple scenes, mocked commands,
output filtering, and more.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Script Syntax](#script-syntax)
- [Contributing](#contributing)
- [License](#license)

## Background

Terminal demos are notoriously hard to reproduce. Screen recordings drift, manual
re-runs produce different output, and polishing timing or hiding sensitive paths
requires video editing.

scriptcast treats demos as code. You write a shell script annotated with `SC`
directives — controlling scenes, typing speed, mocked commands, and output filters —
then run it through a two-stage pipeline: the script executes with shell tracing
enabled, capturing raw output to a `.sc` file; a renderer then synthesises a polished
asciinema cast from that file, one per scene.

The result is a demo you can version-control, diff, and regenerate.

## Install

```bash
pip install scriptcast
```

**Dependencies:** Requires Python 3.10+. For GIF output, install
[agg](https://github.com/asciinema/agg).

### From source

```bash
git clone https://github.com/dacrystal/scriptcast.git
cd scriptcast
pip install -e .
```

## Usage

```bash
# End-to-end: record script and generate all scene casts
scriptcast demo.sh

# Stage 1 only: record to .sc file
scriptcast record demo.sh

# Stage 2 only: generate .cast files from a recorded .sc
scriptcast generate demo.sc

# Generate GIFs from a recorded .sc (requires agg)
scriptcast gif demo.sc
```

Key flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir PATH` | same dir as input | Where to write output files |
| `--directive-prefix PREFIX` | `SC` | Directive prefix used in scripts |
| `--trace-prefix CHAR` | `+` | PS4/trace prefix |
| `--title` / `--no-title` | off | Show scene name at start of each cast |
| `--shell PATH` | `$SHELL` | Shell to use for recording |

## Script Syntax

Scripts are valid shell scripts. `SC` directives are embedded as shell no-ops
(`: SC ...`) so they run without effect but appear in the trace output for the
renderer to consume.

```sh
#!/usr/bin/env scriptcast

# Global config
: SC set type_speed 40
: SC set width 100
: SC set height 28

# --- Scene: Intro ---
: SC scene Intro

echo "Hello from scriptcast"

# --- Scene: Mocked command ---
: SC scene Mocked

mock mycmd <<'EOF'
Starting process...
Done.
EOF

# --- Scene: Output filtering ---
: SC scene Filter

: SC filter sed 's#/home/user#~#g'
pwd

# --- Scene: Pause / resume ---
: SC scene Setup

: SC record pause
APP_DIR="my-app"   # this runs but is NOT recorded
: SC record resume

echo "$APP_DIR"
```

### SC Directives

| Directive | Description |
|-----------|-------------|
| `SC scene <name>` | Start a new scene (one `.cast` per scene) |
| `SC set <key> <value>` | Set timing/display config (see table below) |
| `SC sleep <ms>` | Pause for N milliseconds |
| `SC record pause` | Stop recording (commands still execute) |
| `SC record resume` | Resume recording |
| `SC filter sed '<expr>'` | Apply sed filter to output lines |
| `SC overlay frame <name>` | Apply a GIF frame overlay |

### Config keys (`SC set`)

| Key | Default | Description |
|-----|---------|-------------|
| `type_speed` | `40` | ms per character when typing commands |
| `cmd_wait` | `80` | ms after typing a command |
| `input_wait` | `40` | ms per character for interactive input |
| `exit_wait` | `120` | ms after last output line of a command |
| `width` | `100` | Terminal width |
| `height` | `28` | Terminal height |
| `theme` | `dark` | Terminal theme |
| `prompt` | `$ ` | Prompt string shown before commands |

## Contributing

Issues and pull requests are welcome at
[github.com/dacrystal/scriptcast](https://github.com/dacrystal/scriptcast/issues).

Before opening a PR, please ensure:
- All tests pass: `uv run pytest`
- New behaviour is covered by tests

## License

MIT © dacrystal
