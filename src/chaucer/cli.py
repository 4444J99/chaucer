"""Command line: transcribe, scan, corpus ingest/triage/render, practice-sheet and manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import corpus as corpus_mod
from . import manifest as manifest_mod
from . import practice as practice_mod
from . import render as render_mod
from . import triage as triage_mod
from .middle_english import entries_from_json, scan_line, transcribe_text, validate


def _load_lexicon(path: str | None):
    if not path:
        return None
    return entries_from_json(json.loads(Path(path).read_text("utf-8")))


def _cmd_transcribe(args: argparse.Namespace) -> int:
    lexicon = _load_lexicon(args.lexicon)
    for spelling, ipa in transcribe_text(args.text, lexicon):
        print(f"{spelling}\t{ipa}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    lexicon = _load_lexicon(args.lexicon)
    status = 0
    for line in args.lines:
        scan = scan_line(line, lexicon)
        result = validate(scan)
        verdict = f"ok ({result.kind})" if result.ok else "FAIL: " + "; ".join(result.reasons)
        print(f"{scan.syllables:>2}  {verdict}  | {line}")
        for word, final_e in scan.final_e_report():
            print(f"      -e  {word}: {final_e}")
        if not result.ok:
            status = 1
    return status


def check_fixture_file(path: Path) -> list[str]:
    """Run a scansion fixture file; return one failure message per mismatch."""
    data = json.loads(path.read_text("utf-8"))
    failures: list[str] = []
    for case in data["lines"]:
        lexicon = entries_from_json(case.get("lexicon", {}))
        scan = scan_line(case["text"], lexicon)
        result = validate(scan)
        label = f"line {case['n']}"
        if scan.syllables != case["syllables"]:
            failures.append(f"{label}: syllables {scan.syllables} != {case['syllables']}")
        if result.kind != case["kind"]:
            failures.append(f"{label}: kind {result.kind!r} != {case['kind']!r}")
        report = [list(pair) for pair in scan.final_e_report()]
        if report != case["final_e"]:
            failures.append(f"{label}: final -e {report} != {case['final_e']}")
    return failures


def _cmd_check_fixtures(args: argparse.Namespace) -> int:
    status = 0
    for name in args.paths:
        failures = check_fixture_file(Path(name))
        if failures:
            status = 1
            print(f"{name}: FAIL")
            for failure in failures:
                print(f"  {failure}")
        else:
            print(f"{name}: ok")
    return status


def _cmd_ingest_corpus(args: argparse.Namespace) -> int:
    lexicon = _load_lexicon(args.lexicon)
    try:
        report = corpus_mod.ingest_file(Path(args.path), lexicon)
    except (OSError, corpus_mod.CorpusError) as exc:
        print(f"ingest-corpus: {exc}", file=sys.stderr)
        return 2
    text = corpus_mod.dumps(report)
    if args.output:
        Path(args.output).write_text(text, "utf-8")
    else:
        sys.stdout.write(text)
    summary = report["summary"]
    print(
        f"{summary['passed']}/{summary['total']} lines pass ({summary['pass_rate']:.2%})",
        file=sys.stderr,
    )
    exact_rate = summary["passed"] / summary["total"]  # the report's pass_rate is rounded
    if args.min_pass_rate is not None and exact_rate < args.min_pass_rate:
        print(f"pass rate below --min-pass-rate {args.min_pass_rate}", file=sys.stderr)
        return 1
    return 0


def _cmd_triage_corpus(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if args.top < 1:
        print("triage-corpus: --top must be at least 1", file=sys.stderr)
        return 2
    try:
        report = triage_mod.triage(
            path.read_bytes(), path.name, path.stem, _load_lexicon(args.lexicon), args.top
        )
    except (OSError, corpus_mod.CorpusError) as exc:
        print(f"triage-corpus: {exc}", file=sys.stderr)
        return 2
    text = corpus_mod.dumps(report)
    if args.output:
        Path(args.output).write_text(text, "utf-8")
    else:
        sys.stdout.write(text)
    base = report["baseline"]
    print(
        f"{base['failed']} failing lines; {report['candidates_considered']} candidates",
        file=sys.stderr,
    )
    return 0


def _cmd_render_report(args: argparse.Namespace) -> int:
    try:
        report = json.loads(Path(args.path).read_text("utf-8"))
        page = render_mod.render_report(report, _load_lexicon(args.lexicon))
        if args.output:
            Path(args.output).write_text(page, "utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"render-report: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not args.output:
        sys.stdout.write(page)
    return 0


def _cmd_practice_sheet(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        lines = corpus_mod.parse_corpus(path.read_bytes(), path.stem)
        chosen = practice_mod.select_lines(lines, args.start, args.count)
        page = practice_mod.render_sheet(
            chosen, path.name, _load_lexicon(args.lexicon), args.per_page
        )
        if args.output:
            Path(args.output).write_text(page, "utf-8")
    except (OSError, ValueError) as exc:  # CorpusError and RenderError are ValueErrors
        print(f"practice-sheet: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not args.output:
        sys.stdout.write(page)
    return 0


def _cmd_manifest(args: argparse.Namespace) -> int:
    try:
        manifest = manifest_mod.load(Path(args.path) if args.path else None)
    except manifest_mod.ManifestError as exc:
        print(f"manifest invalid: {exc}", file=sys.stderr)
        return 1
    if args.check:
        print(f"manifest ok: {len(manifest.all_source_ids)} source ids")
    else:
        print(json.dumps(manifest.data, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaucer", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("transcribe", help="Middle English text to syllabified IPA")
    t.add_argument("text")
    t.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    t.set_defaults(func=_cmd_transcribe)

    s = sub.add_parser("scan", help="scan and validate lines for final -e behaviour")
    s.add_argument("lines", nargs="+")
    s.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    s.set_defaults(func=_cmd_scan)

    c = sub.add_parser(
        "check-fixtures", help="verify scansion fixture files (n, text, syllables, kind, final_e)"
    )
    c.add_argument("paths", nargs="+")
    c.set_defaults(func=_cmd_check_fixtures)

    i = sub.add_parser(
        "ingest-corpus",
        help="validate a file of verse lines (ref<TAB>text) and write a JSON report",
    )
    i.add_argument("path")
    i.add_argument("--output", "-o", help="write the report here instead of stdout")
    i.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    i.add_argument(
        "--min-pass-rate",
        type=float,
        help="exit 1 if the pass rate (0-1) is lower; otherwise failures leave the exit code 0",
    )
    i.set_defaults(func=_cmd_ingest_corpus)

    tr = sub.add_parser(
        "triage-corpus",
        help="rank lexicon changes (syncope, no final -e) by net corpus lines fixed",
    )
    tr.add_argument("path")
    tr.add_argument("--output", "-o", help="write the triage here instead of stdout")
    tr.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    tr.add_argument("--top", type=int, default=40, help="candidates to keep (default 40)")
    tr.set_defaults(func=_cmd_triage_corpus)

    r = sub.add_parser(
        "render-report", help="render an ingest-corpus report as a self-contained HTML page"
    )
    r.add_argument("path", help="report JSON written by ingest-corpus")
    r.add_argument("--output", "-o", help="write the page here instead of stdout")
    r.add_argument("--lexicon", help="the lexicon the report was made with, if any")
    r.set_defaults(func=_cmd_render_report)

    p = sub.add_parser(
        "practice-sheet",
        help="printable handwriting-practice sheet (ruled rows, tracing model) for verse lines",
    )
    p.add_argument("path", help="corpus file (ref<TAB>text rows)")
    p.add_argument("--start", help="reference of the first line (default: the first line)")
    p.add_argument("--count", type=int, default=12, help="number of lines (default 12)")
    p.add_argument(
        "--per-page",
        type=int,
        default=practice_mod.DEFAULT_LINES_PER_PAGE,
        help="lines per printed page (default 3)",
    )
    p.add_argument("--output", "-o", help="write the page here instead of stdout")
    p.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    p.set_defaults(func=_cmd_practice_sheet)

    m = sub.add_parser("manifest", help="print or validate the source-thread manifest")
    m.add_argument("--path", help="manifest file (default: the packaged manifest)")
    m.add_argument("--check", action="store_true", help="validate only")
    m.set_defaults(func=_cmd_manifest)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
