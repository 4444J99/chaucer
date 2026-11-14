"""Extract the General Prologue verse lines from Skeat's Canterbury Tales text.

Input is the Project Gutenberg #22120 plain-text file (``22120-8.txt``, ISO-8859-1,
Skeat, *The Complete Works of Geoffrey Chaucer*, vol. 4, Clarendon Press, 1900).
Output is ``ref<TAB>text`` lines. Verse text is copied unchanged apart from removing the
leading indent and the printed line number at the right margin; apparatus (headings,
variant-reading notes, page markers) is dropped. Line numbers are counted sequentially and
checked against the printed numbers; any disagreement aborts. Skeat's bracketed spurious
lines (printed "252 b") keep their own refs and are outside the count.

Usage: python scripts/extract_skeat_gp.py PATH/TO/22120-8.txt > corpus/chaucer_gp_skeat.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

START = "GROUP A. THE PROLOGUE."
END = "THE KNIGHTES TALE."
PAGE_MARK = re.compile(r"^\s*\[\d+: T\. \d+-\d+\.\]\s*$")
# Verse is separated from right-margin matter by a gap of three or more spaces. The margin holds
# either a line number ("10", spurious-line "252 b", alternative "(260)") or a gloss ("KNIGHT.").
GAP = re.compile(r"\s{3,}")
MARGIN_NO = re.compile(r"^(?P<n>\d+)(?: (?P<sfx>[a-z]))?$|^\((?P<alt>\d+)\)$")


def extract(text: str) -> list[tuple[str, str]]:
    lines = text.replace("\r\n", "\n").split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.strip() == START)
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == END)
    block = lines[start + 1 : end]
    # paragraphs separated by blank lines; a paragraph whose first line begins with
    # HEADING or a line number is variant-reading apparatus, not verse
    paras: list[list[str]] = [[]]
    for ln in block:
        if ln.strip():
            paras[-1].append(ln)
        else:
            paras.append([])
    verse: list[tuple[str, str]] = []
    n = 0
    for para in paras:
        para = [ln for ln in para if not PAGE_MARK.match(ln)]
        if not para:
            continue
        first = para[0].strip()
        if first.startswith(("HERE BIGINNETH", "HERE ENDETH", "HEADING.", "*")):
            continue
        if re.match(r"^\d+[.,]", first):
            continue
        for ln in para:
            body, *rest = GAP.split(ln.strip(), maxsplit=1)
            m = MARGIN_NO.match(rest[0].strip()) if rest else None
            printed = suffix = None
            if m and m.group("n"):
                printed, suffix = int(m.group("n")), m.group("sfx")
            if suffix:
                # Skeat's bracketed spurious lines (e.g. "252 b") sit outside the count
                verse.append((f"GP.{printed}{suffix}", body))
                continue
            n += 1
            if printed is not None and printed != n:
                raise SystemExit(f"line count {n} != printed number {printed}: {ln!r}")
            verse.append((f"GP.{n}", body))
    return verse


def main() -> int:
    raw = Path(sys.argv[1]).read_bytes().decode("iso-8859-1")
    for ref, body in extract(raw):
        print(f"{ref}\t{body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
