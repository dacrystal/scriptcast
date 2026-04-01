# Changelog

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
