# Privacy Policy

`session-bridge` processes local conversation logs and writes normalized session data to a local SQLite database.

## Data Handling

- The tool reads local files from paths you explicitly provide or default provider history directories.
- The tool writes to a local SQLite file (default: `.bridge/session-bridge.sqlite`).
- The tool does not include built-in telemetry or remote upload behavior.

## Sensitive Data

- Import pipelines sanitize common secret patterns (for example bearer tokens and API keys).
- Redaction is best effort and not a full DLP system.
- You remain responsible for protecting local files and backups.

## Data Retention

Data remains on your machine until you delete the SQLite store and any imported logs.

## Contact

For privacy questions, open an issue at:
`https://github.com/Biglone/session-bridge/issues`
