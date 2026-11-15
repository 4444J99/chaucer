"""Scansion of the General Prologue's opening lines against hand-derived fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chaucer.middle_english import entries_from_json, scan_line, validate

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "gp_opening.json").read_text("utf-8"))
LINES = FIXTURE["lines"]


def _scan(case):
    return scan_line(case["text"], entries_from_json(case.get("lexicon", {})))


def test_fixture_covers_the_first_eleven_lines():
    assert [c["n"] for c in LINES] == list(range(1, 12))


@pytest.mark.parametrize("case", LINES, ids=lambda c: f"GP.{c['n']}")
def test_syllable_count(case):
    assert _scan(case).syllables == case["syllables"]


@pytest.mark.parametrize("case", LINES, ids=lambda c: f"GP.{c['n']}")
def test_final_e_report(case):
    assert [list(p) for p in _scan(case).final_e_report()] == case["final_e"]


@pytest.mark.parametrize("case", LINES, ids=lambda c: f"GP.{c['n']}")
def test_line_validates_as_pentameter(case):
    result = validate(_scan(case))
    assert result.ok, result.reasons
    assert result.kind == case["kind"]
    assert result.syllables == case["syllables"]


def test_ignoring_elision_would_break_the_lines_that_need_it():
    """Lines 2, 3 and 11 only reach their count because a final -e elides."""
    for n in (2, 3, 11):
        case = LINES[n - 1]
        scan = _scan(case)
        elided = [w for w in scan.words if w.final_e in ("elided_vowel", "elided_h")]
        assert elided, f"GP.{n} should contain an elision"
        assert scan.syllables + len(elided) in (11, 12)
        assert scan.syllables + len(elided) != case["syllables"]


def test_ye_homograph_needs_the_lexicon_entry():
    case = LINES[9]
    bare = scan_line(case["text"])
    assert bare.syllables == 10  # pronoun reading: one syllable
    assert _scan(case).syllables == 11
