"""Rule-level tests for final -e behaviour, independent of the fixtures."""

from __future__ import annotations

import pytest

from chaucer.middle_english import scan_line, validate_line
from chaucer.middle_english.scansion import (
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


def test_lexicon_pronunciation_drives_elision_trigger():
    """Review finding: a homograph override must also work as the *next* word."""
    from chaucer.middle_english import LexEntry

    eye = {"ye": LexEntry(ipa="ˈiː.ə", core=1, final_e=True)}
    assert begins_with_elidable("ye") is None  # spelling: y + vowel glide, consonant
    assert begins_with_elidable("ye", eye) == "vowel"
    bare = scan_line("swete ye")
    with_eye = scan_line("swete ye", eye)
    assert dict(bare.final_e_report())["swete"] == PRONOUNCED
    assert dict(with_eye.final_e_report())["swete"] == ELIDED_VOWEL
    # Bare: swe-te + one-syllable pronoun ye. With "eye": swet + two-syllable ye.
    assert [w.syllables for w in bare.words] == [2, 1]
    assert [w.syllables for w in with_eye.words] == [1, 2]
    # An override that makes a vowel-spelled word consonant-initial blocks elision.
    consonantal = {"ale": LexEntry(ipa="ˈjaː.lə", core=1, final_e=True)}
    assert begins_with_elidable("ale", consonantal) is None
    # h-initial lexicon entries still honour the weak-h list.
    assert begins_with_elidable("hir", {"hir": LexEntry(ipa="hɪr")}) == "h"
    assert begins_with_elidable("hert", {"hert": LexEntry(ipa="hɛrt")}) is None


def test_lexicon_ending_overrides_the_spelling_derived_schwa():
    """Review finding: removing the final schwa must remove the feminine ending."""
    from chaucer.middle_english import LexEntry, analyze

    stressed_end = {"melodye": LexEntry(ipa="mɛ.lɔ.ˈdiː", core=3, final_e=False)}
    assert analyze("melodye").ends_in_schwa
    assert not analyze("melodye", stressed_end).ends_in_schwa
    # Eight monosyllables plus the three-syllable stressed-final word: 11, not feminine.
    line = "that that that that that that that that melodye"
    assert validate_line(line).syllables == 12  # default reading is 4 syllables
    eleven = "that that that that that that that melodye"
    default = validate_line(eleven)
    assert default.syllables == 11 and default.ok  # feminine under the default entry
    overridden = validate_line(eleven, stressed_end)
    assert overridden.syllables == 10 and overridden.ok and overridden.kind == "masculine"
    nonfeminine = validate_line("that that that that that that that that melodye", stressed_end)
    assert nonfeminine.syllables == 11 and not nonfeminine.ok
    assert "schwa" in nonfeminine.reasons[0]
    # No ipa given: final_e=False on a word whose schwa came only from the final -e.
    no_ipa = {"halve": LexEntry(core=2, final_e=False)}
    assert not analyze("halve", no_ipa).ends_in_schwa
    # Inflectional -es is kept as a schwa ending when only final_e is overridden.
    assert analyze("croppes", {"croppes": LexEntry(core=2)}).ends_in_schwa
