"""Corpus ingestion: run the final -e scansion validator over a file of verse lines.

Input format, one verse line per row; blank rows and rows starting with ``#`` are skipped:

* ``ref<TAB>text`` uses ``ref`` as the text reference;
* a row without a tab gets the reference ``<file stem>:<row number>`` (1-based, counting
  every row of the file).

The report is deterministic: no timestamps, sorted keys, and a SHA-256 of the input bytes so a
report can be tied to the exact corpus file. The validator is run unchanged; failures are
recorded, not corrected.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .middle_english import Lexicon, scan_line, validate

SCHEMA = "chaucer.corpus-report/1"


class CorpusError(ValueError):
    """Raised when a corpus file cannot be ingested."""


@dataclass(frozen=True)
class CorpusLine:
    ref: str
    text: str


def parse_corpus(data: bytes, stem: str = "corpus") -> list[CorpusLine]:
    """Parse corpus bytes (UTF-8) into lines; raise :class:`CorpusError` on bad input."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusError(f"corpus is not valid UTF-8: {exc}") from exc
    lines: list[CorpusLine] = []
    seen: set[str] = set()
    for number, row in enumerate(text.splitlines(), start=1):
        if not row.strip() or row.lstrip().startswith("#"):
            continue
        if "\t" in row:
            ref, _, body = row.partition("\t")
            ref, body = ref.strip(), body.strip()
            if not ref or not body:
                raise CorpusError(f"row {number}: empty reference or text")
        else:
            ref, body = f"{stem}:{number}", row.strip()
        if ref in seen:
            raise CorpusError(f"row {number}: duplicate reference {ref!r}")
        seen.add(ref)
        lines.append(CorpusLine(ref, body))
    if not lines:
        raise CorpusError("corpus has no verse lines")
    return lines


def ingest(
    data: bytes, source_name: str, stem: str, lexicon: Lexicon | None = None
) -> dict[str, Any]:
    """Validate every line and return the report mapping."""
    results = []
    for line in parse_corpus(data, stem):
        scan = scan_line(line.text, lexicon)
        verdict = validate(scan)
        results.append(
            {
                "ref": line.ref,
                "text": line.text,
                "ok": verdict.ok,
                "kind": verdict.kind,
                "syllables": verdict.syllables,
                "reasons": list(verdict.reasons),
            }
        )
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    return {
        "schema": SCHEMA,
        "source": {"file": source_name, "sha256": hashlib.sha256(data).hexdigest()},
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 4),
        },
        "lines": results,
    }


def ingest_file(path: Path, lexicon: Lexicon | None = None) -> dict[str, Any]:
    """Read a corpus file and ingest it."""
    return ingest(path.read_bytes(), path.name, path.stem, lexicon)


def dumps(report: dict[str, Any]) -> str:
    """Serialise a report deterministically."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
