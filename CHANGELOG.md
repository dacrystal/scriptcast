# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `--xtrace-log` flag: saves raw PTY xtrace output to `<stem>.xtrace` for debugging

### Fixed
- Frame bar title now defaults to `"Terminal"` instead of empty (was never rendering)
- Export progress bar shown during GIF rendering

---

## [0.1.0] - 2026-04-01

### Added
- `SC scene` — split recording into named scenes; `--split-scenes` for per-scene `.cast` files
- `SC mock` — replace a command's output with fixed text during recording
- `SC expect` — drive interactive sessions via `expect(1)`, capturing input events
- `SC filter` / `SC filter-add` — pipe output through shell commands during recording
- `SC record pause` / `SC record resume` — suppress output sections
- `SC set` — configure timing, dimensions, prompt, and theme per scene
- `SC '\' comment` — inject visual comment lines into the cast
- `SC word_speed` — per-scene word typing speed
- `HelpersDirective` — shared shell helper injection for directive adapters
- Frame layout system: title bar, traffic-light buttons, shadow, border, background, rounded corners
- Theme system: built-in `dark`, `light`, and `aurora` themes; fully configurable via CLI flags
- ScriptCast watermark with DM Sans and Pacifico fonts
- PNG and GIF export via `agg`; PIL-based compositor for frame chrome
- APNG output support
- Stable GIF palette across frames (eliminates chrome color flickering)
- Unified CLI: single `scriptcast` entry point with `--no-export`, `--output-dir`, `--format` flags
- Plugin system: third-party directives via `scriptcast.directives` entry points
- JSONL `.sc` format: timestamped `cmd`, `output`, `input`, `directive` events
- Two-stage pipeline: `record` (`.sh` → `.sc`) and `generate` (`.sc` → `.cast`)
- Verbatim xtrace capture: preserves exact shell trace output in `.sc` file
- Multi-pass directive pipeline: preprocessing, recording, and postprocessing stages
- Bash and zsh shell adapters
- `--xtrace-log` raw PTY capture flag
- `examples/tutorial.sh` and `examples/showcase.sh` as reference scripts

### Fixed
- Decode `\xNN` and `\NNN` escape sequences in SC directive xtrace lines
- Filter directive applied to trace/cmd lines (was only applied to output)
- Frame rendering: shadow, border, theme parsing, SVG filter corrections
- Stable GIF palette: reserved palette slots for exact chrome colors
- CI test suite: ruff lint errors, mypy overrides, agg-dependent test skipping

[Unreleased]: https://github.com/dacrystal/scriptcast/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dacrystal/scriptcast/releases/tag/v0.1.0
