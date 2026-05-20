# Security

## Supported versions

Security fixes target the current `main` branch until a stable release line exists.

## Reporting a vulnerability

Please report security issues privately to the project maintainer before opening a public issue. Include reproduction steps, affected commands, and any relevant input files or URLs.

## Notes for contributors

- Treat `kb ingest add-url` as untrusted network input.
- Avoid adding automatic execution of ingested content.
- Keep model API keys out of this project. `kb-manager` does not require model credentials; model access is configured in OpenClaw.
