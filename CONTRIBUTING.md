# Contributing

Thanks for contributing to `session-bridge`.

## Development Setup

1. Clone the repository.
2. Create a local virtual environment.
3. Install editable dependencies.

```bash
git clone https://github.com/Biglone/session-bridge.git
cd session-bridge
./scripts/setup_venv.sh
```

## Run Tests

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Run Packaging Checks

```bash
npm run release:check
```

## Pull Request Guidelines

- Keep changes focused and small when possible.
- Add or update tests for behavior changes.
- Update docs when command behavior or flags change.
- Keep `README.md`, `docs/quickstart.md`, and `skills/session-bridge/SKILL.md` consistent.

## Commit and Release

- Follow semantic versioning in both `pyproject.toml` and `package.json`.
- Add release notes in `CHANGELOG.md` before tagging.
- Use `vX.Y.Z` tags for releases.
