# Contributing to scriptcast

## Dev Setup

```bash
git clone https://github.com/dacrystal/scriptcast.git
cd scriptcast
pip install -e ".[dev]"
```

## Running Tests

```bash
make test          # pytest with coverage
make lint          # ruff
make typecheck     # mypy
make all           # all three
```

All three must pass before opening a PR. CI enforces this.

## Commit Messages

Use conventional commits — the changelog is generated from them:

- `feat: add SC highlight directive`
- `fix: expect session drops last output line`
- `docs: clarify filter-add chaining`
- `chore: bump ruff version`

## Writing a Directive

See [DIRECTIVES.md](DIRECTIVES.md) for the full guide.

## Pull Request Checklist

- [ ] Tests pass locally (`make all`)
- [ ] New behaviour is covered by tests
- [ ] CHANGELOG.md has an entry (or the auto-PR from CI will add one)
- [ ] DIRECTIVES.md updated if you added or changed a directive

## Release Process (maintainers only)

1. Ensure `CHANGELOG.md` is up to date
2. Bump version in `pyproject.toml`
3. `git tag v0.X.0 && git push --tags`
4. The `release.yml` workflow publishes to PyPI and creates a GitHub Release

PyPI uses Trusted Publisher (OIDC) — no API key needed. Configure at:
pypi.org → your project → Publishing → Add publisher (environment: `release`)
