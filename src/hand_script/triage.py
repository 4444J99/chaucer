"""Counterfactual triage of corpus failures.

The pass rate says how many lines fail, not why. For every word that occurs in a
failing line this module asks: if the lexicon gave that word one fewer syllable
(syncope or a monosyllabic reading), or no final -e, how many corpus lines would
change verdict? ``gain`` is lines newly passing minus lines newly failing across
the whole corpus, so a word that helps one line and breaks three scores negative.

This is evidence for choosing the next lexicon entries, not a source of truth:
the validator is the oracle, so a positive gain shows a candidate worth checking
against the edition and the scholarship, never that the reading is right.
"""

from __future__ import annotations

from typing import Any

from .corpus import CorpusLine, parse_corpus
from .middle_english.lexicon import LexEntry, Lexicon, merge
from .middle_english.phonology import WORD_RE, analyze, normalize
from .middle_english.scansion import validate_line

SCHEMA = "hand-script.triage/1"
VARIANTS = ("no_final_e", "syncope")


def _passing(lines: list[CorpusLine], lexicon: Lexicon) -> set[str]:
    return {ln.ref for ln in lines if validate_line(ln.text, lexicon).ok}


def _variant_entry(word: str, base: Lexicon, variant: str) -> LexEntry | None:
    analysis = analyze(word, base)
    if variant == "no_final_e":
        if not analysis.final_e:
            return None
        return LexEntry(core=analysis.core, final_e=False)
    if analysis.core < 2:  # a one-syllable core cannot lose a syllable and stay a word
        return None
    return LexEntry(core=analysis.core - 1, final_e=analysis.final_e)


def triage(
    data: bytes, source_name: str, stem: str, lexicon: Lexicon | None = None, top: int = 40
) -> dict[str, Any]:
    """Rank candidate lexicon changes by the net number of lines they would fix."""
    lines = parse_corpus(data, stem)
    base = merge(lexicon)
    passing = _passing(lines, base)
    # A lexicon entry only reaches the lines that contain its word, so each trial
    # re-validates just those lines instead of the whole corpus.
    by_word: dict[str, list[CorpusLine]] = {}
    failing_words: dict[str, set[str]] = {}
    for ln in lines:
        for word in {normalize(raw) for raw in WORD_RE.findall(ln.text)} - {""}:
            by_word.setdefault(word, []).append(ln)
            if ln.ref not in passing:
                failing_words.setdefault(word, set()).add(ln.ref)
    candidates = []
    for word in sorted(failing_words):
        for variant in VARIANTS:
            entry = _variant_entry(word, base, variant)
            if entry is None:
                continue
            trial = dict(base)
            trial[word] = entry
            after = _passing(by_word[word], trial)
            touched = {ln.ref for ln in by_word[word]}
            fixed = sorted(after - passing)
            broken = sorted((touched & passing) - after)
            candidates.append(
                {
                    "word": word,
                    "variant": variant,
                    "in_failing_lines": len(failing_words[word]),
                    "fixed": len(fixed),
                    "broken": len(broken),
                    "gain": len(fixed) - len(broken),
                    "fixed_refs": fixed[:5],
                }
            )
    candidates.sort(key=lambda c: (-c["gain"], -c["in_failing_lines"], c["word"], c["variant"]))
    return {
        "schema": SCHEMA,
        "source": {"file": source_name},
        "baseline": {
            "total": len(lines),
            "passed": len(passing),
            "failed": len(lines) - len(passing),
        },
        "candidates": candidates[:top],
        "candidates_considered": len(candidates),
    }
