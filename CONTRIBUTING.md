# Contributing to model-ledger

## Development Setup

```bash
git clone https://github.com/block/model-ledger.git
cd model-ledger
uv sync --all-extras
uv run pytest
```

## Making Changes

1. Fork the repository and create a feature branch
2. Write tests first (TDD)
3. Run the full suite: `uv run pytest -v`
4. Lint and format: `uv run ruff check . && uv run ruff format .`
5. Commit with DCO sign-off: `git commit --signoff`
6. Submit a pull request

## Commit Convention

PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add EU AI Act compliance profile
fix: handle missing owner field in SR 11-7 validation
docs: update quickstart example
test: add property-based tests for model roundtrips
```

## Developer Certificate of Origin

All commits must include a DCO sign-off line:

```
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit --signoff` (or `-s`) to add this automatically.
