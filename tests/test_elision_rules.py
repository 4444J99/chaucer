"""Rule-level tests for final -e behaviour, independent of the fixtures."""

from __future__ import annotations

import pytest

from hand_script.middle_english import scan_line, validate_line
from hand_script.middle_english.scansion import (
    ABSENT,
    ELIDED_H,
    ELIDED_VOWEL,
    LINE_END,
    PRONOUNCED,
    begins_with_elidable,
)


def status(line: str, word: str) -> str:
    return dict(scan_line(line).final_e_report()).get(word, ABSENT)


@pytest.mark.parametrize(
    ("line", "word", "expected"),
    [
        ("tendre croppes", "tendre", PRONOUNCED),
        ("yonge sonne", "yonge", PRONOUNCED),
        ("yonge sonne", "sonne", LINE_END),
        ("smale ek", "smale", ELIDED_VOWEL),
        ("smale up", "smale", ELIDED_VOWEL),
        ("swete hir", "swete", ELIDED_H),
        ("swete hem", "swete", ELIDED_H),
        ("swete hath", "swete", ELIDED_H),
        ("swete honour", "swete", ELIDED_H),
        ("swete hert", "swete", PRONOUNCED),
        ("swete holt", "swete", PRONOUNCED),
        ("swete hors", "swete", PRONOUNCED),
        ("swete yong", "swete", PRONOUNCED),
        ("swete yronne", "swete", ELIDED_VOWEL),
        ("swete wyn", "swete", PRONOUNCED),
    ],
)
def test_final_e_status(line, word, expected):
    assert status(line, word) == expected


def test_elision_removes_exactly_one_syllable():
    pronounced = scan_line("swete bred").syllables
    elided = scan_line("swete ale").syllables
    assert (pronounced, elided) == (3, 3 - 1 + 1)  # swe-te bred = 3; swet ale = 3 (ale: a-le)
    assert scan_line("smale ek").syllables == scan_line("smal ek").syllables


def test_line_final_e_is_kept_and_counts():
    assert scan_line("the roote").syllables == 3  # the + roo-te


def test_monosyllables_with_only_e_are_not_final_e():
    for w in ("the", "he", "she", "me", "we", "ne"):
        assert status(f"{w} bred", w) == ABSENT


def test_inflectional_endings_do_not_elide():
    # -es is a syllable and is not removed before a vowel: crop-pes and = 3 syllables.
    assert scan_line("croppes and").syllables == 3


def test_begins_with_elidable_classification():
    assert begins_with_elidable("ale") == "vowel"
    assert begins_with_elidable("yronne") == "vowel"
    assert begins_with_elidable("yonge") is None
    assert begins_with_elidable("hir") == "h"
    assert begins_with_elidable("honour") == "h"
    assert begins_with_elidable("hert") is None
    assert begins_with_elidable("whan") is None
    assert begins_with_elidable("") is None


def test_validator_rejects_wrong_lengths_and_masculine_eleven():
    short = validate_line("Whan that Aprille")
    assert not short.ok and "syllables" in short.reasons[0]
    # melodye elides before eek, giving eleven syllables with a monosyllabic last word:
    # eleven without a feminine ending is rejected.
    eleven = validate_line("And smale foweles maken melodye eek")
    assert not eleven.ok
    assert eleven.syllables == 11
    assert "schwa" in eleven.reasons[0]
    long = validate_line("The tendre croppes and the yonge sonne bright")
    assert not long.ok
    assert long.syllables == 12
