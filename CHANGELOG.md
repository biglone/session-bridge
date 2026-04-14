# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

## [0.1.11] - 2026-04-15

### Fixed
- fixed GitHub Actions expression validation by removing direct `secrets.*` usage in `if` conditions and handling missing tokens inside shell steps.

## [0.1.10] - 2026-04-15

### Changed
- hardened GitHub Actions release flow to check whether the npm version is already published before `npm publish`, preventing duplicate-version failures when a manual publish happens first.

## [0.1.9] - 2026-04-15

### Changed
- refreshed NPM package metadata (`description`, discoverability `keywords`) to better reflect current features (`shim`, `resume-latest`, SSH clipboard/OSC52, cross-provider continuity).
- improved README and publish guide messaging to align package listing copy with actual CLI capabilities.

## [0.1.8] - 2026-04-15

### Fixed
- `bridge shim run` now shields restore from `SIGINT/SIGTERM` interruptions so pressing `Ctrl+C` in the wrapped `codex` process no longer leaves partially-restored provider metadata.
- `bridge shim run` restore error handling now catches `KeyboardInterrupt` and other `BaseException` cases, returning a controlled error with manual-restore hint instead of traceback abort.

## [0.1.7] - 2026-04-15

### Added
- `bridge shim apply` to snapshot and rewrite Codex thread `model_provider` metadata for one project, including rollout JSONL backup and SQLite row backup.
- `bridge shim restore` to revert a shim run (latest pending by default) with conflict checks and optional `--force`.
- `bridge shim status` to inspect recent shim runs under `.bridge/provider-shim`.
- `bridge shim run` wrapper to auto-apply shim, execute a command (default `codex`), then auto-restore.

### Changed
- provider shim internals now fall back safely when rollout paths are outside `codex_home` and tolerate thread schemas missing `updated_at`.
- `bridge shim apply` / `bridge shim run` now auto-detect `--target-provider` from `~/.codex/config.toml` top-level `model_provider` when flag is omitted.

## [0.1.6] - 2026-04-14

### Added
- `bridge help` subcommand (including `bridge help <command>`) as an alias-style help entrypoint.
- new `bridge copy-local` command to run remote `resume-latest` via SSH and copy output into local clipboard.

### Changed
- clipboard copy now falls back to OSC52 terminal escape in environments without `pbcopy/wl-copy/xclip/xsel` (for example SSH sessions), improving `resume-latest --copy` behavior.

## [0.1.5] - 2026-04-14

### Added
- new `bridge version` command to print the current installed CLI/package version.

### Changed
- `bridge resume-latest` now defaults to clipboard mode and supports `--no-copy` to force terminal output.

## [0.1.4] - 2026-04-14

### Added
- `bridge resume` and `bridge resume-latest` now support `--copy` to write generated resume context directly to system clipboard and print a concise continuation hint.

### Changed
- clarified docs that `resume` / `resume-latest` default to `--max-turns 20`.

## [0.1.3] - 2026-04-14

### Added
- `bridge list` and `bridge resume-latest` now also auto-scan home-level `~/.codex` history so same-project sessions remain visible across provider/account switches.

### Changed
- added CLI flags for home-level scan control:
  - `--home-codex-dir`
  - `--home-codex-limit`
  - `--no-scan-home-codex`
- expanded tests to cover home-level fallback scanning behavior.

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

[Unreleased]: https://github.com/Biglone/session-bridge/compare/v0.1.11...HEAD
[0.1.11]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.11
[0.1.10]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.10
[0.1.9]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.9
[0.1.8]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.8
[0.1.7]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.7
[0.1.6]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.6
[0.1.5]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.5
[0.1.4]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.4
[0.1.3]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.3
[0.1.2]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.2
[0.1.1]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.1
[0.1.0]: https://github.com/Biglone/session-bridge/releases/tag/v0.1.0
