.PHONY: lint typecheck test all \
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
	touch CHANGELOG.md
	git cliff --unreleased --prepend CHANGELOG.md --bump
	@echo "CHANGELOG.md updated. Review, then run: make release"

# Full release: update changelog, commit, tag, push
release:
	$(eval VERSION := $(shell git cliff --bumped-version))
	touch CHANGELOG.md
	git cliff --unreleased --prepend CHANGELOG.md --bump
	git add CHANGELOG.md
	git commit -m "chore: release $(VERSION)"
	git tag $(VERSION)
	git push origin main --tags
	@echo "Released $(VERSION)"
