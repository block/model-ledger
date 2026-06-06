"""MkDocs hook: emit AI-native docs artifacts at build time.

Produces three things in the built site, with zero extra dependencies:

* ``/llms.txt``       — a curated, <5KB index of every page (the llmstxt.org spec)
* ``/llms-full.txt``  — the full corpus, concatenated, for deep ingestion
* ``/<page>.md``      — the raw Markdown of every page, fetchable by IDE agents

This is deliberately a local hook rather than a plugin: it is small, fully under
our control, and means model-ledger's own docs are natively consumable by any
agent — fitting for a project whose product *is* an MCP server.

Spec: https://llmstxt.org/
"""

from __future__ import annotations

import os
import re
import shutil

# Top-level nav groups, in order, for the llms.txt index.
_SECTIONS = [
    ("Start here", ("index.md", "quickstart.md")),
    ("Concepts", ("concepts/",)),
    ("Guides", ("guides/",)),
    ("Recipes", ("recipes/",)),
    ("Reference", ("reference/",)),
]

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_FM_BLOCK = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_NOISE = re.compile(r"[*`_>#\[\]]|\(http[^)]*\)|&[a-z]+;")


def _fm_field(text: str, field: str) -> str:
    """Read a single-line frontmatter field (the curated source of truth)."""
    block = _FM_BLOCK.match(text)
    if not block:
        return ""
    m = re.search(rf"^{field}:\s*(.+)$", block.group(1), re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else ""


def _iter_pages(docs_dir: str):
    """Yield (relpath, raw_text) for every Markdown page worth indexing."""
    for root, _dirs, files in os.walk(docs_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            abspath = os.path.join(root, fname)
            rel = os.path.relpath(abspath, docs_dir).replace(os.sep, "/")
            if rel.startswith("superpowers/"):
                continue
            with open(abspath, encoding="utf-8") as fh:
                yield rel, fh.read()


def _title(text: str, fallback: str) -> str:
    # Curated frontmatter title wins; else first real H1 (HTML stripped); else path.
    fm = _fm_field(text, "title")
    if fm:
        return fm
    body = _CODE_FENCE.sub("", _FRONTMATTER.sub("", text))
    m = _H1.search(body)
    return _HTML_TAG.sub("", m.group(1)).strip() if m else fallback


def _summary(text: str) -> str:
    """Curated frontmatter description, else first real sentence of prose."""
    fm = _fm_field(text, "description")
    if fm:
        return fm
    body = _CODE_FENCE.sub("", _FRONTMATTER.sub("", text))
    body = _HTML_TAG.sub("", body)
    for block in body.split("\n\n"):
        line = block.strip()
        if not line or line.startswith(("#", "|", "- ", "* ", "+ ", "!!!", ">")):
            continue
        clean = _MD_NOISE.sub("", line).replace("\n", " ").strip()
        if len(clean) > 24:
            return (clean[:157] + "…") if len(clean) > 158 else clean
    return ""


def _section_for(rel: str) -> int:
    for i, (_label, prefixes) in enumerate(_SECTIONS):
        if rel in prefixes or any(p.endswith("/") and rel.startswith(p) for p in prefixes):
            return i
    return len(_SECTIONS)  # "More", catch-all


def on_post_build(config, **_kwargs) -> None:  # noqa: ANN001
    docs_dir = config["docs_dir"]
    site_dir = config["site_dir"]
    site_url = (config.get("site_url") or "").rstrip("/")
    site_name = config.get("site_name", "model-ledger")
    site_desc = config.get("site_description", "")

    pages = list(_iter_pages(docs_dir))

    # 1. Per-page raw Markdown, mirrored at the same relative path.
    for rel, _text in pages:
        dest = os.path.join(site_dir, rel)
        os.makedirs(os.path.dirname(dest) or site_dir, exist_ok=True)
        shutil.copyfile(os.path.join(docs_dir, rel), dest)

    # 2. llms.txt — curated index grouped by nav section.
    buckets: dict[int, list[tuple[str, str]]] = {}
    for rel, text in pages:
        idx = _section_for(rel)
        title = _title(text, rel)
        summary = _summary(text)
        url = f"{site_url}/{rel}" if site_url else rel
        line = f"- [{title}]({url})" + (f": {summary}" if summary else "")
        buckets.setdefault(idx, []).append((rel, line))

    # Sort each section with its index page first, then alphabetically by path.
    def _key(item: tuple[str, str]):
        rel = item[0]
        return (not rel.endswith("index.md"), rel)

    out = [f"# {site_name}", ""]
    if site_desc:
        out += [f"> {site_desc.strip()}", ""]
    section_names = [s[0] for s in _SECTIONS] + ["More"]
    for idx in sorted(buckets):
        out.append(f"## {section_names[idx]}")
        out.append("")
        out.extend(line for _rel, line in sorted(buckets[idx], key=_key))
        out.append("")
    with open(os.path.join(site_dir, "llms.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip() + "\n")

    # 3. llms-full.txt — the whole corpus for deep ingestion.
    full = [f"# {site_name} — full documentation\n"]
    if site_desc:
        full.append(f"> {site_desc.strip()}\n")
    for rel, text in pages:
        body = _FRONTMATTER.sub("", text).strip()
        full.append(f"\n\n---\n\n# source: {rel}\n\n{body}")
    with open(os.path.join(site_dir, "llms-full.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(full).rstrip() + "\n")

    print(f"  llms_txt hook: wrote llms.txt, llms-full.txt, and {len(pages)} per-page .md files")
