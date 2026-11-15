"""Render a corpus report as one self-contained HTML page.

The page shows the pass rate, a syllable-count histogram and every verse line with its verdict.
Inside each line, a final -e is marked by what the validator did with it: counted (green),
elided before a vowel or weak h (struck through), or kept at the line end. The report supplies
the verdicts; each line is re-scanned only to learn the per-word final -e behaviour, and the
re-scan must reproduce the report's syllable count or :class:`RenderError` is raised (for
example when the report was made with a lexicon that is not passed again).

The output is deterministic (no timestamps, no network, no scripts) so it can be committed and
compared with a fresh render.
"""

from __future__ import annotations

import html
from collections import Counter
from typing import Any

from .corpus import SCHEMA
from .middle_english import Lexicon, scan_line
from .middle_english.phonology import WORD_RE
from .middle_english.scansion import (
    ABSENT,
    ELIDED_H,
    ELIDED_VOWEL,
    LINE_END,
    PRONOUNCED,
    Scansion,
)

_STATUS_CLASS = {
    PRONOUNCED: "e-sounded",
    ELIDED_VOWEL: "e-elided",
    ELIDED_H: "e-elided",
    LINE_END: "e-lineend",
}
_STATUS_LABEL = {
    PRONOUNCED: "final -e counted",
    ELIDED_VOWEL: "final -e elided before a vowel",
    ELIDED_H: "final -e elided before weak h",
    LINE_END: "line-final -e kept",
}

_CSS = """
:root {
  color-scheme: light dark;
  --bg: #faf7f0; --fg: #2a2520; --muted: #6f665b; --rule: #ddd5c6;
  --ok: #2f6b3a; --bad: #a3342b; --accent: #7a4a1e; --bar: #b9a88a;
  --sound: #d6ebd2; --lineend: #cfe0f3;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1c1a17; --fg: #ebe4d6; --muted: #a39a8b; --rule: #3b362e;
    --ok: #7fc48b; --bad: #e57f74; --accent: #d9a872; --bar: #6b604b;
    --sound: #274a2d; --lineend: #23405e;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px 64px; background: var(--bg); color: var(--fg);
  font: 16px/1.5 Georgia, "Iowan Old Style", serif;
}
main { max-width: 860px; margin: 0 auto; }
h1 { margin: 0 0 4px; font-size: 1.6rem; color: var(--accent); }
.meta { color: var(--muted); font-size: 0.85rem; word-break: break-all; }
.stats { display: flex; flex-wrap: wrap; gap: 24px; margin: 20px 0 8px; }
.stat b { display: block; font-size: 1.8rem; line-height: 1.1; }
.stat span { color: var(--muted); font-size: 0.85rem; }
.meter { height: 10px; border-radius: 5px; background: var(--rule); overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--ok); }
.hist { margin: 20px 0; }
.hist h2, .legend h2 { font-size: 0.95rem; margin: 0 0 6px; color: var(--muted); }
.hrow { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
.hrow .n { width: 2.5em; text-align: right; color: var(--muted); }
.hrow .bar { height: 12px; background: var(--bar); border-radius: 2px; }
.hrow.good .bar { background: var(--ok); }
.hrow .c { color: var(--muted); }
.legend { margin: 16px 0; font-size: 0.9rem; }
.legend span.k { margin-right: 14px; white-space: nowrap; }
.filters { display: flex; gap: 8px; margin: 20px 0 8px; }
.filters label {
  padding: 4px 12px; border: 1px solid var(--rule); border-radius: 14px;
  cursor: pointer; font-size: 0.9rem;
}
#f-all:checked ~ .filters label[for="f-all"],
#f-pass:checked ~ .filters label[for="f-pass"],
#f-fail:checked ~ .filters label[for="f-fail"] {
  background: var(--accent); color: var(--bg); border-color: var(--accent);
}
.filters-radio { position: absolute; opacity: 0; pointer-events: none; }
#f-pass:checked ~ .lines .line.fail { display: none; }
#f-fail:checked ~ .lines .line.pass { display: none; }
.line {
  display: grid; grid-template-columns: 4.6em 8.5em 1fr; gap: 4px 12px;
  padding: 7px 0; border-top: 1px solid var(--rule); align-items: baseline;
}
.ref { color: var(--muted); font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.badge { font-size: 0.8rem; font-weight: bold; white-space: nowrap; }
.pass .badge { color: var(--ok); }
.fail .badge { color: var(--bad); }
.text { font-size: 1.05rem; }
.reason { grid-column: 3; color: var(--bad); font-size: 0.85rem; }
.e-sounded { background: var(--sound); border-radius: 2px; }
.e-lineend { background: var(--lineend); border-radius: 2px; }
.e-elided { text-decoration: line-through; color: var(--muted); }
.w-sounded { background: var(--sound); border-radius: 2px; }
.w-lineend { background: var(--lineend); border-radius: 2px; }
.w-elided { text-decoration: line-through; color: var(--muted); }
@media (max-width: 520px) {
  .line { grid-template-columns: 3.6em 1fr; }
  .reason { grid-column: 1 / -1; }
  .text { grid-column: 1 / -1; }
}
"""


class RenderError(ValueError):
    """Raised when a report cannot be rendered faithfully."""


def _word_html(raw: str, status: str) -> str:
    """Return one word with its final -e wrapped according to ``status``."""
    escaped_title = html.escape(_STATUS_LABEL[status], quote=True)
    cls = _STATUS_CLASS[status]
    if raw[-1:] in ("e", "E") and len(raw) > 1:
        return (
            f'{html.escape(raw[:-1])}<span class="{cls}" title="{escaped_title}">{raw[-1]}</span>'
        )
    # the final -e comes from a lexicon entry or is not a plain trailing e: style the word
    word_cls = "w-" + cls.removeprefix("e-")
    return f'<span class="{word_cls}" title="{escaped_title}">{html.escape(raw)}</span>'


def line_html(text: str, scan: Scansion) -> str:
    """Return ``text`` as HTML with each word's final -e marked.

    The original text is walked as a whole, so punctuation and spacing between words are kept
    exactly; the i-th word match pairs with the i-th word of the scan.
    """
    matches = list(WORD_RE.finditer(text))
    if len(matches) != len(scan.words):
        raise RenderError(f"{text!r}: {len(matches)} words in text, {len(scan.words)} scanned")
    out: list[str] = []
    cursor = 0
    for match, word in zip(matches, scan.words, strict=True):
        out.append(html.escape(text[cursor : match.start()]))
        raw = match.group(0)
        if word.final_e == ABSENT:
            out.append(html.escape(raw))
        else:
            out.append(_word_html(raw, word.final_e))
        cursor = match.end()
    out.append(html.escape(text[cursor:]))
    return "".join(out)


def _histogram(rows: list[dict[str, Any]]) -> str:
    counts = Counter(r["syllables"] for r in rows)
    peak = max(counts.values())
    out = []
    for n in range(min(counts), max(counts) + 1):
        count = counts.get(n, 0)
        width = round(100 * count / peak, 1)
        good = " good" if n in (10, 11) else ""
        out.append(
            f'<div class="hrow{good}"><span class="n">{n}</span>'
            f'<span class="bar" style="width:{width}%"></span>'
            f'<span class="c">{count}</span></div>'
        )
    return "\n".join(out)


def _line_row(row: dict[str, Any], lexicon: Lexicon | None) -> str:
    scan = scan_line(row["text"], lexicon)
    if scan.syllables != row["syllables"]:
        raise RenderError(
            f"{row['ref']}: re-scan gives {scan.syllables} syllables, report says "
            f"{row['syllables']} (was the report made with a --lexicon?)"
        )
    state = "pass" if row["ok"] else "fail"
    badge = f"ok {html.escape(str(row['kind']))}" if row["ok"] else "FAIL"
    parts = [
        f'<div class="line {state}">',
        f'<span class="ref">{html.escape(row["ref"])}</span>',
        f'<span class="badge">{badge} · {row["syllables"]}</span>',
        f'<span class="text">{line_html(row["text"], scan)}</span>',
    ]
    parts.extend(f'<span class="reason">{html.escape(reason)}</span>' for reason in row["reasons"])
    parts.append("</div>")
    return "\n".join(parts)


def render_report(report: dict[str, Any], lexicon: Lexicon | None = None) -> str:
    """Return the HTML page for a corpus report mapping."""
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        schema = report.get("schema") if isinstance(report, dict) else type(report).__name__
        raise RenderError(f"unsupported report schema {schema!r}")
    rows = report["lines"]
    summary = report["summary"]
    source = report["source"]
    if not isinstance(rows, list) or not rows:
        raise RenderError("report has no lines")
    passed = sum(1 for r in rows if r["ok"])
    expected = {"total": len(rows), "passed": passed, "failed": len(rows) - passed}
    if {k: summary.get(k) for k in expected} != expected:
        raise RenderError(f"report summary {summary!r} does not match its lines {expected!r}")
    kinds = Counter(r["kind"] for r in rows if r["ok"])
    percent = f"{100 * summary['passed'] / summary['total']:.2f}"
    title = f"Scansion report: {source['file']}"
    legend = (
        '<span class="k"><span class="e-sounded">e</span> final -e counted</span>'
        '<span class="k"><span class="e-elided">e</span> elided before a vowel or weak h</span>'
        '<span class="k"><span class="e-lineend">e</span> line-final, kept (feminine ending)</span>'
    )
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
        f'<p class="meta">sha256 {html.escape(source["sha256"])}</p>',
        '<div class="stats">',
        f'<div class="stat"><b>{percent}%</b><span>{summary["passed"]} of '
        f"{summary['total']} lines pass</span></div>",
        f'<div class="stat"><b>{kinds.get("masculine", 0)}</b><span>masculine (10)</span></div>',
        f'<div class="stat"><b>{kinds.get("feminine", 0)}</b><span>feminine (11)</span></div>',
        f'<div class="stat"><b>{summary["failed"]}</b><span>fail</span></div>',
        "</div>",
        f'<div class="meter"><i style="width:{percent}%"></i></div>',
        f'<div class="hist"><h2>Syllables per line</h2>\n{_histogram(rows)}</div>',
        f'<div class="legend"><h2>Final -e</h2>{legend}</div>',
        '<input class="filters-radio" type="radio" name="f" id="f-all" checked>',
        '<input class="filters-radio" type="radio" name="f" id="f-pass">',
        '<input class="filters-radio" type="radio" name="f" id="f-fail">',
        '<div class="filters"><label for="f-all">all</label>'
        '<label for="f-pass">pass</label><label for="f-fail">fail</label></div>',
        '<div class="lines">',
    ]
    body = [_line_row(row, lexicon) for row in rows]
    tail = ["</div>", "</main></body>", "</html>", ""]
    return "\n".join(head + body + tail)
