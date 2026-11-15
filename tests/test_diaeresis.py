"""A diaeresis letter (ë, ï, ...) is part of a word, not a word boundary."""

from __future__ import annotations

from chaucer.middle_english import scan_line
from chaucer.middle_english.phonology import normalize


def test_normalize_folds_diaeresis_to_base_letter():
    assert normalize("yë") == "ye"
    assert normalize("sëynt") == "seynt"
    assert normalize("vigilyës") == "vigilyes"
    assert normalize("Ïs") == "is"


def test_diaeresis_word_is_not_split():
    scan = scan_line("Hir gretteste ooth was but by sëynt Loy")
    assert [w.word for w in scan.words] == [
        "Hir",
        "gretteste",
        "ooth",
        "was",
        "but",
        "by",
        "sëynt",
        "Loy",
    ]


def test_diaeresis_word_uses_its_lexicon_entry():
    scan = scan_line("That slepen al the night with open yë")
    last = scan.words[-1]
    assert (last.word, last.ipa, last.syllables) == ("yë", "jeː", 1)


def test_transcribe_text_keeps_diaeresis_words_whole():
    from chaucer.middle_english.phonology import transcribe_text

    pairs = transcribe_text("yë sëynt treës")
    assert [spelling for spelling, _ in pairs] == ["yë", "sëynt", "treës"]
