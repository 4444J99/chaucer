"""Final -e scansion validator for Chaucerian verse.

Chaucer's decasyllabic line (iambic pentameter) counts a historically
pronounced final -e as a syllable, except that it elides:

1. before a word beginning with a vowel (``droghte of`` scans ``drogh'of``);
2. before ``h`` in the weak function words and French words with a silent h
   (``veyne hir`` elides; ``yonge hert`` does not);
3. never at the end of the line, where the -e is kept and yields the
   feminine (eleven-syllable) ending.

The validator reports, for every word, what happened to its final -e, then
checks the line total: 10 (masculine) or 11 (feminine, requiring a schwa-final
last syllable). It checks syllable *count* and final -e behaviour; it does not
claim to verify the stress pattern.

Scope limits stated plainly: only plain -e is elided. Inflectional -es/-ed/-en/
-eth are counted as syllables and are not elided; lines whose scansion needs
syncope or an unusual inflection must carry a lexicon entry (see ``lexicon``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .lexicon import Lexicon, merge
from .phonology import WordPhonology, analyze, normalize, tokenize

# Words in which an initial h elides (weak h): pronouns and auxiliaries.
WEAK_H_WORDS = frozenset(
    {"he", "him", "his", "hir", "hire", "hem", "hath", "have", "haven", "hadde", "hadden", "had"}
    | {"hast", "han", "hap"}
)
# French-derived words with silent initial h.
SILENT_H_WORDS = frozenset(
    {"honour", "honur", "honest", "honeste", "hostiler", "hostelrye", "hour", "houre", "heir"}
)

_WORD = re.compile(r"[A-Za-zþðȝæÞÐȜÆ]+")

PRONOUNCED = "pronounced"
ELIDED_VOWEL = "elided_vowel"
ELIDED_H = "elided_h"
LINE_END = "line_end"
ABSENT = "absent"


IPA_VOWELS = frozenset("aeiouyɛɔɪʊəæ")


def begins_with_elidable(word: str, lexicon: Lexicon | None = None) -> str | None:
    """Return ``"vowel"`` or ``"h"`` if a preceding final -e would elide, else ``None``.

    The initial sound comes from the lexicon pronunciation when the word has an
    entry (so a homograph override such as ``ye`` "eye" elides a preceding -e),
    and from the spelling otherwise.
    """
    norm = normalize(word)
    if not norm:
        return None
    entry = merge(lexicon).get(norm)
    if entry is not None and entry.ipa:
        first = entry.ipa.lstrip("ˈˌ")[:1]
        if first in IPA_VOWELS:
            return "vowel"
        if first == "h" and (norm in WEAK_H_WORDS or norm in SILENT_H_WORDS):
            return "h"
        return None
    if norm[0] == "h":
        if norm in WEAK_H_WORDS or norm in SILENT_H_WORDS:
            return "h"
        return None
    units = tokenize(norm)
    if units and units[0].kind == "V":
        return "vowel"
    return None


@dataclass(frozen=True)
class WordScan:
    word: str
    ipa: str
    final_e: str  # one of PRONOUNCED, ELIDED_VOWEL, ELIDED_H, LINE_END, ABSENT
    syllables: int


@dataclass(frozen=True)
class Scansion:
    line: str
    words: tuple[WordScan, ...]
    syllables: int
    feminine_ending: bool

    def final_e_report(self) -> list[tuple[str, str]]:
        """``(word, status)`` for every word that has a final -e."""
        return [(w.word, w.final_e) for w in self.words if w.final_e != ABSENT]


@dataclass(frozen=True)
class Validation:
    ok: bool
    syllables: int
    kind: str | None  # "masculine", "feminine" or None when the line fails
    reasons: tuple[str, ...]


def scan_line(line: str, lexicon: Lexicon | None = None) -> Scansion:
    """Scan one line, resolving each word's final -e."""
    lex = merge(lexicon)
    raw_words = _WORD.findall(line)
    analyses: list[WordPhonology] = [analyze(w, lex) for w in raw_words]
    scanned: list[WordScan] = []
    last = len(raw_words) - 1
    for i, (raw, a) in enumerate(zip(raw_words, analyses, strict=True)):
        if not a.final_e:
            scanned.append(WordScan(raw, a.ipa, ABSENT, a.syllables))
            continue
        if i == last:
            scanned.append(WordScan(raw, a.ipa, LINE_END, a.syllables))
            continue
        trigger = begins_with_elidable(raw_words[i + 1], lex)
        if trigger == "vowel":
            scanned.append(WordScan(raw, a.ipa, ELIDED_VOWEL, a.core))
        elif trigger == "h":
            scanned.append(WordScan(raw, a.ipa, ELIDED_H, a.core))
        else:
            scanned.append(WordScan(raw, a.ipa, PRONOUNCED, a.syllables))
    total = sum(w.syllables for w in scanned)
    feminine = bool(analyses) and analyses[-1].ends_in_schwa and analyses[-1].syllables > 1
    return Scansion(line, tuple(scanned), total, feminine)


def validate(scansion: Scansion) -> Validation:
    """Check a scanned line against decasyllabic (10 or feminine 11) pentameter."""
    n = scansion.syllables
    if n == 10:
        return Validation(True, n, "masculine", ())
    if n == 11:
        if scansion.feminine_ending:
            return Validation(True, n, "feminine", ())
        return Validation(
            False, n, None, ("11 syllables but the last word has no unstressed schwa ending",)
        )
    return Validation(False, n, None, (f"{n} syllables; pentameter needs 10 or feminine 11",))


def validate_line(line: str, lexicon: Lexicon | None = None) -> Validation:
    """Scan and validate in one step."""
    return validate(scan_line(line, lexicon))
