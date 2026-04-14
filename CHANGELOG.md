# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

## [0.1.2] - 2026-04-14

### Added
- `bridge list` and `bridge resume-latest` now auto-scan and import project-local `.codex` rollout history before reading the bridge store.
- project-local multi-account Codex layouts are unified automatically (for example `./.codex/account-a/sessions` + `./.codex/account-b/sessions`).

## [0.1.1] - 2026-04-14

### Added
- npm `postinstall` automation to auto-run plugin registration on global install.
- environment switches for install behavior:
  - `SESSION_BRIDGE_SKIP_AUTO_INSTALL=1` to skip auto-registration
  - `SESSION_BRIDGE_AUTO_INSTALL=1` to force registration for local install

### Changed
- quickstart and README updated for global install, upgrade, and verification workflow.

## [0.1.0] - 2026-04-14

### Added
- SQLite bridge store for normalized cross-provider session metadata and turns.
- CLI commands: `init`, `list`, `resume`, `resume-latest`.
- Import adapters: `import-codex`, `import-claude`, `import-all`.
- Plugin installer command: `install-plugin`.
- Secret redaction for common token and key patterns.
- Repository consistency section in resume output.
- NPM launcher with Python runtime bootstrap support.

[Unreleased]: https://github.com/Biglone/session-bridge/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.2
[0.1.1]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.1
[0.1.0]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.0
