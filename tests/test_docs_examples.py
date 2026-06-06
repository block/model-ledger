"""Execute the runnable code examples in the docs so they can't drift.

The API reference is generated from source (mkdocstrings/Griffe) and `mkdocs
build --strict` catches broken references and links. The remaining drift risk is
hand-written prose: a tutorial snippet that calls an API that has since changed.

This test closes that hole. For every docs page it extracts the ```python code
blocks (including the indented ones inside content tabs), runs each page's blocks
together in a single namespace — mirroring how a reader follows the page top to
bottom — and fails if any of them raise. If the SDK changes in a way that breaks a
documented example, this test goes red on the PR.

Blocks that require external resources (a live Snowflake/HTTP connection, boto3,
a real database, a GitHub token) can't run in CI; they're skipped via EXTERNAL
markers. Pages whose examples are purely illustrative are listed in SKIP_FILES.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"

# Substrings that mark a block as needing an external resource we can't provide
# in CI. Such a block is illustrative and skipped (not executed).
EXTERNAL = (
    "boto3",
    "ghp_",
    "from_snowflake",
    "HttpLedgerBackend",
    "mlflow",
    "sql_connector(",
    "rest_connector(",
    "github_connector(",
    "sqlite3.connect",
    "snowflake",
    "my_db",
    "= source",
)

# Pages whose examples assume pre-existing state (e.g. members discovered
# elsewhere) and are intentionally illustrative rather than self-contained.
SKIP_FILES = {
    "concepts/composite.md",  # members are assumed already registered/discovered
}

_FENCE = re.compile(r"^(?P<indent>[ \t]*)```(?P<lang>\S*)\s*$")


def _python_blocks(md: str) -> list[str]:
    """Extract python fenced blocks, dedenting tab-indented ones."""
    blocks: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        indent, lang = m.group("indent"), m.group("lang").lower()
        i += 1
        body: list[str] = []
        close = re.compile(rf"^{re.escape(indent)}```\s*$")
        while i < len(lines) and not close.match(lines[i]):
            line = lines[i]
            body.append(line[len(indent) :] if line.startswith(indent) else line)
            i += 1
        i += 1  # consume closing fence
        if lang in ("python", "py"):
            blocks.append("\n".join(body))
    return blocks


def _runnable(md: str) -> str:
    """Concatenate the runnable python blocks of a page into one program."""
    blocks = [b for b in _python_blocks(md) if not any(tok in b for tok in EXTERNAL)]
    return "\n\n".join(blocks)


_DOC_FILES = sorted(
    p
    for p in DOCS.rglob("*.md")
    # superpowers/ holds internal planning specs — not on the site, not tested
    if not p.relative_to(DOCS).as_posix().startswith("superpowers/")
    and p.relative_to(DOCS).as_posix() not in SKIP_FILES
)


@pytest.mark.parametrize("md_path", _DOC_FILES, ids=lambda p: p.relative_to(DOCS).as_posix())
def test_doc_examples_run(md_path: Path, tmp_path, monkeypatch) -> None:
    code = _runnable(md_path.read_text(encoding="utf-8"))
    if not code.strip():
        pytest.skip("no runnable python blocks")
    monkeypatch.chdir(tmp_path)  # any file writes (e.g. ./inventory.db) land in tmp
    namespace: dict = {}
    exec(compile(code, str(md_path), "exec"), namespace)  # noqa: S102
