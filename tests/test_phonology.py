"""Transcriber tests: the rule outputs this project commits to."""

from __future__ import annotations

import pytest

from hand_script.middle_english import analyze, transcribe, transcribe_text
from hand_script.middle_english.phonology import normalize, syllabify, tokenize


@pytest.mark.parametrize(
    ("word", "ipa"),
    [
        ("nyght", "nɪçt"),  # gh after a front vowel is [ç]
        ("droghte", "ˈdrɔx.tə"),  # gh after a back vowel is [x]
        ("sweete", "ˈsweː.tə"),
        ("shoures", "ˈʃuː.rəs"),  # French ou = [uː]
        ("perced", "ˈpɛr.səd"),  # c before e = [s], -ed is a schwa syllable
        ("bathed", "ˈbaː.ðəd"),  # intervocalic th is voiced
        ("sonne", "ˈsʊn.nə"),  # geminate split, scribal o for [u]
        ("longen", "ˈlɔŋ.gən"),  # ng is [ŋg]
        ("thing", "θɪŋg"),
        ("holt", "hɔlt"),
        ("heeth", "heːθ"),
        ("corages", "kɔ.ˈraː.dʒəs"),  # Romance ending attracts stress; g before e = [dʒ]
        ("nature", "na.ˈtyː.rə"),
        ("inspired", "ɪn.ˈspiː.rəd"),  # unstressed prefix in-
        ("yronne", "ɪ.ˈrʊn.nə"),  # y- prefix is a vowel, stress shifts off it
        ("whan", "hwan"),
        ("knyght", "knɪçt"),
    ],
)
def test_transcription(word, ipa):
    assert transcribe(word) == ipa


def test_lexicon_overrides_rules_and_is_flagged():
    assert analyze("every").from_lexicon
    assert transcribe("every") == "ˈɛv.rɪ"
    assert not analyze("holt").from_lexicon


def test_caller_lexicon_wins():
    from hand_script.middle_english import LexEntry

    custom = {"holt": LexEntry(ipa="ˈhɔlt.ə", core=1, final_e=True)}
    assert transcribe("holt", custom) == "ˈhɔlt.ə"
    assert analyze("holt", custom).syllables == 2


def test_syllable_counts_exclude_final_e_from_core():
    a = analyze("halve")
    assert (a.core, a.final_e, a.syllables) == (1, True, 2)
    b = analyze("the")
    assert (b.core, b.final_e) == (1, False)
    c = analyze("melodye")
    assert (c.core, c.final_e, c.syllables) == (3, True, 4)


def test_normalize_folds_medieval_letters():
    assert normalize("Þat") == "that"
    assert normalize("ȝe") == "ye"
    assert normalize("Aprille,") == "aprille"


def test_tokenizer_units():
    assert [u.text for u in tokenize("sweete")] == ["s", "w", "ee", "t", "e"]
    assert [u.text for u in tokenize("yonge")] == ["y", "o", "ng", "e"]
    assert tokenize("yonge")[0].kind == "C"  # y + vowel is the glide
    assert tokenize("yronne")[0].kind == "V"  # y + consonant is the prefix vowel
    assert tokenize("sonne")[2].long  # geminate nn


def test_syllabification_maximal_onset():
    spell = lambda w: [s.spelling for s in syllabify(tokenize(w))]  # noqa: E731
    assert spell("aprille") == ["a", "pril", "e"]  # the geminate ll is one unit
    assert spell("nature") == ["na", "tu", "re"]
    assert spell("croppes") == ["crop", "es"]  # geminate pp closes the first syllable


def test_transcribe_text_returns_pairs_and_skips_punctuation():
    pairs = transcribe_text("Whan that, Aprille!")
    assert [p[0] for p in pairs] == ["Whan", "that", "Aprille"]
    assert pairs[0][1] == "hwan"
