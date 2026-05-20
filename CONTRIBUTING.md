# Contributing

Thanks for improving kb-manager. Keep changes small, tested, and aligned with the project's current zero-runtime-dependency design.

## Development setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
./.venv/bin/python -m pytest tests/
```

Without pytest installed, the standard-library regression tests can still be run:

```bash
python3 -m unittest tests.test_index_regressions
```

## Change guidelines

- Add or update tests for behavior changes in indexing, search, ingest, lint, or frontmatter parsing.
- Keep the CLI deterministic and local-first.
- Do not add model-provider dependencies to the CLI. Model reasoning is supplied by the host OpenClaw Agent, not this package.
- Document any new environment variable in README and `skills/kb-manager/SKILL.md`.
