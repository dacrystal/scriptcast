## [0.3.0] - 2026-04-07

### Added

- Fix default theme loading and zsh xtrace ESC byte corruption ([#1](https://github.com/dacrystal/scriptcast/issues/1))

## [0.2.0] - 2026-04-06

### Added

- Add --version, ASCII banner, hatch-fancy-pypi-readme, and GitHub Pages workflow

## [0.1.0] - 2026-04-06

### Added

- SC mock/expect directives, InputLine event, single-cast default
- Add expect example to basic.sh; fix recorder cwd and send_user newline
- JSONL .sc format, streaming generator, expect session improvements
- FilterDirective subprocess command; add CommentDirective
- Open source readiness — directive plugin system, CLI fix, CI/CD, community files
- Typing_word_speed, GIF frame overlay, dev tooling
- Frame layout system with CLI flags for title bar, shadow, background, and watermark
- Add theme system, scriptcast watermark, and frame layout refactor
- SVG-based chrome renderer with APNG output support
- PIL fallback frame parity — content masking, APNG, GIF palette fix
- Replace gif subcommand with export — content-first compositor
- Add terminal content pre-processing pipeline
- Frame bool, dark theme full config, CLI cleanup, DM Sans watermark
- CLI simplification
- Export format png, temp gif, aurora/light themes, aurora FrameConfig defaults
- Complete basic.sh, README demo, and xtrace quoting fixes
- Unify config pipeline — ThemeConfig nested in ScriptcastConfig, theme.py deleted
- *(examples)* Redesign demo — showcase.sh, tutorial.sh, fake-myapp
- Multi-pass directive pipeline redesign
- Verbatim xtrace capture + PTY recording
- Unified CLI — single entry point, --no-export flag, config resolved before recording
- HelpersDirective + PTY read simplification + three bug fixes
- --xtrace-log flag + export progress bar + frame-bar-title fix

### Changed

- Remove _handle_passthrough; directives own SC syntax matching
- Replace SVG chrome rendering with PIL-only chrome+mask approach
- Codebase cleanup and best-practices refactor

### Fixed

- CI test failure and ruff lint errors from recent features
- Ignore missing PIL stubs in mypy (Pillow is optional)
- Stable GIF palette across frames — eliminates chrome color flickering
- Reserve palette slots for exact chrome colors in GIF output
- Frame rendering bug fixes — shadow, border, theme parsing, SVG filter
- Decode \xNN and \NNN escape sequences in SC directive xtrace lines
- *(filter)* Apply filter to trace/cmd lines and decouple from ExpectDirective
- Resolve CI test failures
- Resolve all mypy errors in scriptcast/

