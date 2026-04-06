.PHONY: lint typecheck test all install-tools \
        changelog changelog-preview changelog-bump release

# ── CI / quality ────────────────────────────────────────────────────────────

lint:
	ruff check .

typecheck:
	mypy scriptcast/

test:
	pytest --cov=scriptcast --cov-report=term-missing

all: lint typecheck test

# ── Changelog / release ──────────────────────────────────────────────────────

# Preview what the next changelog entry will look like (dry-run, no files changed)
changelog-preview:
	git cliff --unreleased --bump

# Show what the next version number will be
changelog-bump:
	git cliff --bumped-version

# Prepend new entries to CHANGELOG.md for the next release
changelog:
	git cliff --prepend --bump
	@echo "CHANGELOG.md updated. Review, then run: make release"

# Full release: update changelog, commit, tag, push
release:
	$(eval VERSION := $(shell git cliff --bumped-version))
	git cliff --prepend --bump
	git add CHANGELOG.md
	git commit -m "chore: release $(VERSION)"
	git tag $(VERSION)
	git push origin main --tags
	@echo "Released $(VERSION)"

# ── Dev tooling: agg binary + JetBrains Mono font ───────────────────────────

BIN            := bin
AGG            := $(BIN)/agg
AGG_BIN        := $(BIN)/.agg-real
FONTS_DIR      := $(BIN)/fonts
FONTS_SENTINEL := $(FONTS_DIR)/.installed

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Linux)
  ifeq ($(UNAME_M),x86_64)
    AGG_ASSET := agg-x86_64-unknown-linux-gnu
  else ifeq ($(UNAME_M),aarch64)
    AGG_ASSET := agg-aarch64-unknown-linux-gnu
  else
    $(error Unsupported Linux architecture: $(UNAME_M))
  endif
else ifeq ($(UNAME_S),Darwin)
  ifeq ($(UNAME_M),arm64)
    AGG_ASSET := agg-aarch64-apple-darwin
  else
    AGG_ASSET := agg-x86_64-apple-darwin
  endif
else
  $(error Unsupported OS: $(UNAME_S))
endif

AGG_URL  := https://github.com/asciinema/agg/releases/latest/download/$(AGG_ASSET)
FONT_URL := https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip

install-tools: $(AGG) $(FONTS_SENTINEL)

$(AGG): $(FONTS_SENTINEL)
	mkdir -p $(BIN)
	curl -fsSL -o $(AGG_BIN) $(AGG_URL)
	chmod +x $(AGG_BIN)
	printf '#!/bin/sh\nexec "$$(dirname "$$0")/.agg-real" --font-dir "$$(dirname "$$0")/fonts" --font-family "JetBrains Mono" "$$@"\n' > $(AGG)
	chmod +x $(AGG)

$(FONTS_SENTINEL):
	mkdir -p $(FONTS_DIR)
	curl -fsSL -o $(FONTS_DIR)/JetBrainsMono.zip $(FONT_URL)
	unzip -q -o $(FONTS_DIR)/JetBrainsMono.zip "fonts/ttf/*.ttf" -d $(FONTS_DIR)
	mv $(FONTS_DIR)/fonts/ttf/*.ttf $(FONTS_DIR)/
	rm -rf $(FONTS_DIR)/fonts $(FONTS_DIR)/JetBrainsMono.zip
	touch $(FONTS_SENTINEL)
