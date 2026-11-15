"""Printable handwriting-practice sheet for Middle English verse lines.

Each chosen line becomes a block: the reference and scansion verdict, the line in print with
each final -e marked as the validator scanned it, the syllabified IPA, then three ruled rows
(ascender, x-height, baseline and descender guides): one with the line as a faint tracing
model, two empty for copying. The sheet is one self-contained HTML page laid out for A4 and
fixed to white paper when printed. It is deterministic (no timestamps, no network, no scripts).

The tracing script is a stand-in: the page asks for a cursive system font and falls back to the
browser's generic cursive. It is not a manuscript hand (Chaucerian secretary or anglicana), and
the sheet does not claim to teach one.
"""

from __future__ import annotations

import html

from .corpus import CorpusLine
from .middle_english import Lexicon, scan_line, validate
from .render import RenderError, line_html

DEFAULT_LINES_PER_PAGE = 3

# Guide geometry in viewBox units (a row is 1000 x 84).
ROW_WIDTH = 1000
ROW_HEIGHT = 84
ASCENDER, XHEIGHT, BASELINE, DESCENDER = 14, 42, 64, 80
MAX_FONT = 46
CHAR_WIDTH = 0.46  # em, generous for the cursive stand-in so long lines stay inside the row

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px; background: #fff; color: #1c1a17;
  font: 16px/1.4 Georgia, "Iowan Old Style", serif;
}
main { max-width: 820px; margin: 0 auto; }
h1 { margin: 0 0 2px; font-size: 1.4rem; color: #7a4a1e; }
.intro { color: #6f665b; font-size: 0.85rem; margin: 0 0 18px; }
.page { break-after: page; }
.page:last-child { break-after: auto; }
.block { break-inside: avoid; margin: 0 0 20px; padding-top: 8px; border-top: 1px solid #ddd5c6; }
.head { display: flex; gap: 12px; align-items: baseline; font-size: 0.85rem; color: #6f665b; }
.head b { color: #1c1a17; }
.ok { color: #2f6b3a; }
.bad { color: #a3342b; }
.model { font-size: 1.5rem; margin: 2px 0 0; }
.ipa { color: #6f665b; font-size: 0.9rem; margin: 0 0 4px; }
.e-sounded { background: #d6ebd2; border-radius: 2px; }
.e-lineend { background: #cfe0f3; border-radius: 2px; }
.e-elided { text-decoration: line-through; color: #6f665b; }
.w-sounded { background: #d6ebd2; border-radius: 2px; }
.w-lineend { background: #cfe0f3; border-radius: 2px; }
.w-elided { text-decoration: line-through; color: #6f665b; }
svg.row { display: block; width: 100%; height: auto; }
svg.row text {
  font-family: "Snell Roundhand", "Apple Chancery", "Segoe Script", "Brush Script MT", cursive;
  fill: #b8b0a2;
}
.guide { stroke-width: 1; fill: none; }
.g-main { stroke: #8a8174; }
.g-soft { stroke: #cfc7b8; stroke-dasharray: 5 5; }
@page { size: A4; margin: 14mm; }
@media print {
  body { padding: 0; background: #fff; }
  .e-sounded, .e-lineend, .w-sounded, .w-lineend { background: none; }
}
"""


def _row_svg(text: str | None) -> str:
    """One ruled row; ``text`` is drawn as a faint tracing model when given."""
    parts = [f'<svg class="row" viewBox="0 0 {ROW_WIDTH} {ROW_HEIGHT}" aria-hidden="true">']
    for y, cls in (
        (ASCENDER, "g-soft"),
        (XHEIGHT, "g-soft"),
        (BASELINE, "g-main"),
        (DESCENDER, "g-soft"),
    ):
        parts.append(f'<line class="guide {cls}" x1="0" y1="{y}" x2="{ROW_WIDTH}" y2="{y}"/>')
    if text:
        size = min(MAX_FONT, round((ROW_WIDTH - 20) / (CHAR_WIDTH * len(text)), 1))
        parts.append(f'<text x="10" y="{BASELINE}" font-size="{size}">{html.escape(text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _block(line: CorpusLine, lexicon: Lexicon | None) -> str:
    scan = scan_line(line.text, lexicon)
    verdict = validate(scan)
    state = (
        f'<span class="ok">ok {html.escape(str(verdict.kind))}</span>'
        if verdict.ok
        else '<span class="bad">scansion fails</span>'
    )
    ipa = " ".join(w.ipa for w in scan.words)
    return "\n".join(
        [
            '<section class="block">',
            f'<div class="head"><b>{html.escape(line.ref)}</b>'
            f"<span>{scan.syllables} syllables</span>{state}</div>",
            f'<p class="model">{line_html(line.text, scan)}</p>',
            f'<p class="ipa">{html.escape(ipa)}</p>',
            _row_svg(line.text),
            _row_svg(None),
            _row_svg(None),
            "</section>",
        ]
    )


def select_lines(lines: list[CorpusLine], start: str | None, count: int) -> list[CorpusLine]:
    """Return ``count`` consecutive lines beginning at reference ``start`` (default: first)."""
    if count < 1:
        raise RenderError("--count must be at least 1")
    index = 0
    if start is not None:
        refs = [ln.ref for ln in lines]
        if start not in refs:
            raise RenderError(f"unknown reference {start!r}")
        index = refs.index(start)
    chosen = lines[index : index + count]
    if len(chosen) < count:
        raise RenderError(f"only {len(chosen)} lines from {chosen[0].ref!r} to the end of the file")
    return chosen


def render_sheet(
    lines: list[CorpusLine],
    source_name: str,
    lexicon: Lexicon | None = None,
    per_page: int = DEFAULT_LINES_PER_PAGE,
) -> str:
    """Return the practice-sheet HTML for ``lines``, ``per_page`` blocks to a printed page."""
    if not lines:
        raise RenderError("no lines to render")
    if per_page < 1:
        raise RenderError("--per-page must be at least 1")
    title = f"Handwriting practice: {lines[0].ref} to {lines[-1].ref}"
    pages = []
    for i in range(0, len(lines), per_page):
        blocks = "\n".join(_block(ln, lexicon) for ln in lines[i : i + per_page])
        pages.append(f'<div class="page">\n{blocks}\n</div>')
    head = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body><main>",
        f"<h1>{html.escape(title)}</h1>",
        f'<p class="intro">{html.escape(source_name)}. Read the line, trace the faint copy, then '
        "write it twice more. Green -e is sounded, struck -e is elided, blue is the line-final "
        "-e. The script is a stand-in, not a manuscript hand.</p>",
    ]
    return "\n".join(head + pages + ["</main></body>", "</html>", ""])
