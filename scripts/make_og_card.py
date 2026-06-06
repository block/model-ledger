#!/usr/bin/env python3
"""Generate the Open Graph social card for the docs site.

Produces a 1200x630 PNG in the "technical-archive" palette (warm paper, ink,
oxblood) so shared links render beautifully in Slack/Twitter/LinkedIn.

Run once and commit the result; it is a static asset, not a build step:

    .venv/bin/python scripts/make_og_card.py

Requires Pillow. Fonts are resolved from the system with graceful fallback.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

PAPER = (247, 243, 236)
INK = (28, 26, 23)
INK_SOFT = (74, 70, 64)
OXBLOOD = (122, 26, 26)
HAIRLINE = (206, 198, 184)

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "og-image.png")

_SERIF = ["/System/Library/Fonts/Supplemental/Georgia.ttf"]
_SERIF_BOLD = ["/System/Library/Fonts/Supplemental/Georgia Bold.ttf"]
_SANS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]
_MONO = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/SFNSMono.ttf"]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _tracked(draw, xy, text, font, fill, tracking):
    """Draw text with manual letter-spacing (PIL has none natively)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def main() -> None:
    img = Image.new("RGB", (1200, 630), PAPER)
    d = ImageDraw.Draw(img)

    # Inset hairline frame — editorial.
    d.rounded_rectangle([28, 28, 1171, 601], radius=10, outline=HAIRLINE, width=2)

    serif_bold = _font(_SERIF_BOLD, 112)
    serif = _font(_SERIF, 33)
    sans = _font(_SANS, 21)
    mono = _font(_MONO, 23)

    # Kicker
    _tracked(d, (74, 92), "OPEN-SOURCE MODEL GOVERNANCE", sans, OXBLOOD, 4)

    # Title
    d.text((70, 150), "git for models.", font=serif_bold, fill=INK)

    # Tagline (two lines)
    line1 = "Discover every model, rule, and pipeline across"
    line2 = "all your platforms as one immutable, queryable graph."
    d.text((74, 312), line1, font=serif, fill=INK_SOFT)
    d.text((74, 356), line2, font=serif, fill=INK_SOFT)

    # Footer
    d.text((74, 545), "block/model-ledger", font=mono, fill=INK)
    w = d.textlength("block/model-ledger", font=mono)
    d.text((74 + w, 545), "   ·   Apache-2.0", font=mono, fill=INK_SOFT)

    # Mini dependency graph, lower-right — the motif, drawn (not animated here).
    nodes = {"a": (852, 462), "b": (986, 398), "c": (986, 528), "d": (1118, 462)}
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
    for u, v in edges:
        d.line([nodes[u], nodes[v]], fill=OXBLOOD, width=3)
    for cx, cy in nodes.values():
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=OXBLOOD)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=PAPER)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {os.path.normpath(OUT)} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
