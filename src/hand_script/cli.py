"""Command line: transcribe, scan and manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import manifest as manifest_mod
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
    parser = argparse.ArgumentParser(prog="hand-script", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("transcribe", help="Middle English text to syllabified IPA")
    t.add_argument("text")
    t.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    t.set_defaults(func=_cmd_transcribe)

    s = sub.add_parser("scan", help="scan and validate lines for final -e behaviour")
    s.add_argument("lines", nargs="+")
    s.add_argument("--lexicon", help="JSON file of extra lexicon entries")
    s.set_defaults(func=_cmd_scan)

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
