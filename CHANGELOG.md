# Changelog

## Unreleased - 2026-04-06

### Features

- `--xtrace-log` flag: saves raw PTY xtrace capture to `<stem>.xtrace` for debugging
- Export progress bar: per-frame progress display during PIL GIF rendering
- `frame-bar-title` now defaults to `"Terminal"` (was empty, preventing title from rendering)

### Fixes

- CI test failures: skip `agg`-dependent tests when `agg` binary is not installed
- Stale tests `test_split_rgba_removed` / `test_build_svg_removed` removed (broken assertions)
- Scene set in `test_integration` updated to include `word_speed` scene from `tutorial.sh`
- Resolved all mypy errors in `scriptcast/` source (font union types, null-safety, untyped def)

### Chore

- All ruff lint errors fixed (import sorting, line length, ambiguous variable names)
- mypy `tests.*` override added to skip `disallow_untyped_defs` on test files

## v0.1.0 - 2026-04-01

### Features

- JSONL `.sc` format: timestamped `cmd`, `output`, `input`, `directive` events
- Two-stage pipeline: `record` (script → `.sc`) and `generate` (`.sc` → `.cast`)
- `SC scene` — split output into multiple cast files or one combined cast
- `SC mock` — replace a command's output with fixed text during recording
- `SC expect` — drive interactive sessions via expect(1), capturing input events
- `SC filter` / `SC filter-add` — pipe output through shell commands during recording
- `SC record pause` / `SC record resume` — suppress output sections
- `SC '\' comment` — inject visual comment lines into the cast
- `SC set` — configure timing, dimensions, prompt, theme per scene
- Bash and zsh shell adapters
- GIF output via `agg`
- `--split-scenes` flag for per-scene `.cast` files
- Plugin system: third-party directives via `scriptcast.directives` entry points
