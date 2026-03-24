# Contributing to model-ledger

Thank you for your interest in contributing to model-ledger!

## Development Setup

```bash
# Clone the repository
git clone git@github.com:block/model-ledger.git
cd model-ledger

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest -v

# Run linter
uv run ruff check .
uv run ruff format --check .
```

## Making Changes

1. Fork the repository and create a branch from `main`.
2. Write tests for your changes (TDD preferred).
3. Run `uv run pytest -v` and ensure all tests pass.
4. Run `uv run ruff check . && uv run ruff format .` for linting.
5. Commit with DCO sign-off: `git commit --signoff`
6. Use conventional commit format for PR titles: `feat(scope): description`

## DCO Sign-Off

All commits must include a DCO (Developer Certificate of Origin) sign-off:

```bash
git commit --signoff -m "feat(sdk): add bulk registration"
```

## Code Style

- Python 3.10+ type hints throughout
- Pydantic 2.x for data models
- ruff for linting and formatting
- pytest for testing

## Block Employees

If you work at Block, see internal documentation for Block-specific integrations and adapters.

## Questions?

Open a discussion on GitHub or reach out on Discord.
