# Release Guide

## Preconditions

- Working tree is clean
- Tests are passing
- Changelog is updated
- Version is updated in both `pyproject.toml` and `package.json`

## Local Release Checks

```bash
npm run release:check
```

## Tag and Publish

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Publish package artifacts:

```bash
npm publish --access public
# Optional PyPI publish
# python3 -m twine upload dist/*
```

## Post Release

- Create GitHub release notes from `CHANGELOG.md`
- Validate install path in a clean environment:

```bash
npx @biglone/session-bridge --help
```
