"""Rule-based phonological transcriber for Chaucerian Middle English.

The engine reads a normalised (Riverside-style) spelling and produces a
syllabified IPA string. It is deliberately explicit about what it models:

* digraph and consonant-cluster reading (``ou`` /uː/, ``gh`` [x]/[ç], ``ng`` [ŋg], ...);
* syllabification by a maximal-onset rule with geminates split across the break;
* vowel quantity from syllable shape (open stressed syllables lengthen);
* stress by lexicon, then by prefix and Romance-ending heuristics, else initial;
* the final -e syllable, which :mod:`hand_script.middle_english.scansion` elides.

Anything the spelling cannot decide lives in :mod:`.lexicon`. This is a
reconstruction aid, not a claim about any single manuscript.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lexicon import LexEntry, Lexicon, merge

VOWEL_LETTERS = frozenset("aeiouy")

# Vowel digraphs (one syllable nucleus each) and their reconstructed value.
VOWEL_DIGRAPHS: dict[str, str] = {
    "ee": "eː",
    "oo": "oː",
    "ea": "ɛː",
    "ai": "ai",
    "ay": "ai",
    "ei": "ɛi",
    "ey": "ɛi",
    "au": "au",
    "aw": "au",
    "ou": "uː",
    "ow": "ou",
    "eu": "ɛu",
    "ew": "ɛu",
    "oi": "ɔi",
    "oy": "ɔi",
}

SHORT_VOWELS = {"a": "a", "e": "ɛ", "i": "ɪ", "y": "ɪ", "o": "ɔ", "u": "ʊ"}
# Stressed open u is the French [y] of loans such as nature, vertu.
LONG_VOWELS = {"a": "aː", "e": "ɛː", "i": "iː", "y": "iː", "o": "ɔː", "u": "yː"}
MONOSYLLABLE_OPEN = {"a": "aː", "e": "eː", "i": "iː", "y": "iː", "o": "oː", "u": "uː"}

CONSONANT_DIGRAPHS = ("tch", "ch", "sh", "th", "wh", "gh", "ck", "ph", "qu")
INITIAL_ONLY_DIGRAPHS = ("kn", "gn", "wr")

CONSONANT_IPA = {
    "ch": "tʃ",
    "tch": "tʃ",
    "sh": "ʃ",
    "wh": "hw",
    "ck": "k",
    "ph": "f",
    "qu": "kw",
    "kn": "kn",
    "gn": "gn",
    "wr": "wr",
    "j": "dʒ",
    "x": "ks",
    "z": "z",
    "v": "v",
    "w": "w",
    "y": "j",
}

# Function words whose initial th- is voiced.
VOICED_TH_WORDS = frozenset(
    {"the", "that", "thee", "thy", "they", "this", "these", "thise", "there", "than", "thanne"}
    | {"thus", "thou", "though", "thogh", "thider"}
)

# Valid syllable onsets (by base letters) for the maximal-onset rule.
ONSETS2 = frozenset(
    {
        ("p", "r"),
        ("b", "r"),
        ("t", "r"),
        ("d", "r"),
        ("k", "r"),
        ("g", "r"),
        ("f", "r"),
        ("p", "l"),
        ("b", "l"),
        ("k", "l"),
        ("g", "l"),
        ("f", "l"),
        ("s", "p"),
        ("s", "t"),
        ("s", "k"),
        ("s", "m"),
        ("s", "n"),
        ("s", "l"),
        ("s", "w"),
        ("t", "w"),
        ("d", "w"),
        ("k", "w"),
    }
)
ONSETS3 = frozenset({("s", "t", "r"), ("s", "p", "r"), ("s", "k", "r"), ("s", "p", "l")})

UNSTRESSED_PREFIXES = frozenset({"be", "y", "en", "in", "de", "re", "con", "com", "ex", "a"})
# Romance endings that attract stress onto the last non-schwa syllable.
ROMANCE_ENDING = re.compile(r"(ure|age|ye|ie|ee|ou|our|oun|ioun|tu|ice|ise)(s)?$")
FRONT_VOWELS = frozenset({"e", "i", "y", "ei", "ey", "ee", "ea"})

_LETTERS = re.compile(r"[^a-z]")


def normalize(word: str) -> str:
    """Lower-case and fold medieval letters to the Riverside-style Latin spelling."""
    w = word.lower().replace("þ", "th").replace("ð", "th").replace("æ", "ae")
    if w.startswith("ȝ"):
        w = "y" + w[1:]
    w = w.replace("ȝ", "gh")
    return _LETTERS.sub("", w)


@dataclass
class Unit:
    """One grapheme unit: a vowel nucleus or a consonant (cluster)."""

    kind: str  # "V" or "C"
    text: str
    final_e: bool = False
    long: bool = False  # geminate, or ng: split across the syllable break
    split: tuple[str, str] | None = None  # (coda part, onset part) in IPA

    @property
    def base(self) -> str:
        """Letter used for onset-cluster checks (c reads as k)."""
        return "k" if self.text == "c" else self.text


@dataclass
class Syllable:
    onset: list[Unit] = field(default_factory=list)
    nucleus: Unit | None = None
    coda: list[Unit] = field(default_factory=list)
    stressed: bool = False
    schwa: bool = False

    @property
    def spelling(self) -> str:
        parts = self.onset + ([self.nucleus] if self.nucleus else []) + self.coda
        return "".join(u.text for u in parts)

    @property
    def is_open(self) -> bool:
        return not self.coda


def tokenize(word: str) -> list[Unit]:
    """Split a normalised word into grapheme units and flag a final -e."""
    w = normalize(word)
    units: list[Unit] = []
    i = 0
    while i < len(w):
        rest = w[i:]
        two = rest[:2]
        if two in VOWEL_DIGRAPHS:
            units.append(Unit("V", two))
            i += 2
            continue
        if i == 0 and rest[:2] in INITIAL_ONLY_DIGRAPHS:
            units.append(Unit("C", rest[:2]))
            i += 2
            continue
        matched = next((d for d in CONSONANT_DIGRAPHS if rest.startswith(d)), None)
        if matched:
            units.append(Unit("C", matched))
            i += len(matched)
            continue
        if two == "ng":
            units.append(Unit("C", "ng", long=True, split=("ŋ", "g")))
            i += 2
            continue
        ch = w[i]
        if ch == "y" and i == 0 and len(w) > 1 and w[1] in "aeiou":
            units.append(Unit("C", "y"))
        elif ch in VOWEL_LETTERS:
            units.append(Unit("V", ch))
        elif units and units[-1].kind == "C" and units[-1].text == ch and units[-1].split is None:
            prev = units[-1]
            prev.long = True
            prev.split = (ch, ch)
        else:
            units.append(Unit("C", ch))
        i += 1
    ends_in_e = bool(units) and units[-1].kind == "V" and units[-1].text == "e"
    if ends_in_e and any(u.kind == "V" for u in units[:-1]):
        units[-1].final_e = True
    return units


def syllabify(units: list[Unit]) -> list[Syllable]:
    """Group units into syllables with a maximal-onset rule."""
    nuclei = [i for i, u in enumerate(units) if u.kind == "V"]
    if not nuclei:
        return []
    syllables = [Syllable(nucleus=units[i]) for i in nuclei]
    syllables[0].onset = list(units[: nuclei[0]])
    syllables[-1].coda = list(units[nuclei[-1] + 1 :])
    for n in range(len(nuclei) - 1):
        run = units[nuclei[n] + 1 : nuclei[n + 1]]
        if not run:
            continue
        onset_len = _onset_length(run)
        cut = len(run) - onset_len
        syllables[n].coda = list(run[:cut])
        syllables[n + 1].onset = list(run[cut:])
    return syllables


def _onset_length(run: list[Unit]) -> int:
    if run[-1].long:
        return 0
    for size, onsets in ((3, ONSETS3), (2, ONSETS2)):
        tail = run[-size:]
        if (
            len(tail) == size
            and not any(u.long for u in tail)
            and tuple(u.base for u in tail) in onsets
        ):
            return size
    return 1


def _is_schwa_position(syl: Syllable, index: int, count: int) -> bool:
    """An unstressed non-initial e closing the word: -e, -es, -ed, -en, -eth, -er."""
    nuc = syl.nucleus
    if nuc is None or nuc.text != "e" or index == 0 or count < 2:
        return False
    return index == count - 1 and len(syl.coda) <= 2


def assign_stress(syllables: list[Syllable]) -> int | None:
    """Mark schwa syllables and the stressed syllable; return the stress index."""
    count = len(syllables)
    for idx, syl in enumerate(syllables):
        syl.schwa = bool(
            syl.nucleus and (syl.nucleus.final_e or _is_schwa_position(syl, idx, count))
        )
    if count == 0:
        return None
    spelling = "".join(s.spelling for s in syllables)
    if count == 1:
        index = 0
    elif ROMANCE_ENDING.search(spelling):
        index = max((i for i, s in enumerate(syllables) if not s.schwa), default=0)
    elif syllables[0].spelling in UNSTRESSED_PREFIXES:
        index = 1
    else:
        index = 0
    syllables[index].stressed = True
    return index


def _consonant_ipa(idx: int, units: list[Unit], word: str) -> str:
    u = units[idx]
    prev = units[idx - 1] if idx > 0 else None
    nxt = units[idx + 1] if idx + 1 < len(units) else None
    text = u.text
    if u.split is not None and text != "ng":
        return u.split[0]
    if text == "ng":
        return "ŋg"
    if text == "gh":
        return "ç" if prev is not None and prev.text in FRONT_VOWELS else "x"
    if text == "c":
        return "s" if nxt is not None and nxt.text[0] in "eiy" else "k"
    if text == "g":
        return "dʒ" if nxt is not None and nxt.text[0] in "eiy" else "g"
    between_vowels = prev is not None and prev.kind == "V" and nxt is not None and nxt.kind == "V"
    if text == "s":
        return "z" if between_vowels else "s"
    if text == "th":
        voiced = between_vowels or (idx == 0 and word in VOICED_TH_WORDS)
        return "ð" if voiced else "θ"
    return CONSONANT_IPA.get(text, text)


def _vowel_ipa(idx: int, units: list[Unit], syl: Syllable, multi: bool) -> str:
    u = units[idx]
    if u.final_e:
        return "ə"
    if u.text in VOWEL_DIGRAPHS:
        return VOWEL_DIGRAPHS[u.text]
    if syl.schwa:
        return "ə"
    letter = u.text
    nxt = units[idx + 1] if idx + 1 < len(units) else None
    # Scribal o for [u] beside minims: sonne, love.
    minim = (
        nxt is not None
        and nxt.kind == "C"
        and ((nxt.text in {"n", "m"} and nxt.long) or nxt.text == "v")
    )
    if letter == "o" and minim:
        return "ʊ"
    if syl.stressed and syl.is_open:
        table = LONG_VOWELS if multi else MONOSYLLABLE_OPEN
        return table.get(letter, SHORT_VOWELS[letter])
    return SHORT_VOWELS[letter]


@dataclass(frozen=True)
class WordPhonology:
    """Everything the transcriber and the scansion validator need for one word."""

    word: str
    ipa: str
    core: int  # syllables excluding a final -e syllable
    final_e: bool  # carries a final -e syllable (elidable)
    ends_in_schwa: bool  # last syllable is an unstressed -e/-es/-ed/-en/-eth/-er syllable
    from_lexicon: bool = False

    @property
    def syllables(self) -> int:
        return self.core + (1 if self.final_e else 0)


def _render(units: list[Unit], syllables: list[Syllable], word: str, stress: int | None) -> str:
    index_of = {id(u): i for i, u in enumerate(units)}
    multi = len(syllables) > 1
    pieces: list[str] = []
    carry = ""
    for n, syl in enumerate(syllables):
        out = carry
        carry = ""
        for u in syl.onset:
            out += _consonant_ipa(index_of[id(u)], units, word)
        assert syl.nucleus is not None
        out += _vowel_ipa(index_of[id(syl.nucleus)], units, syl, multi)
        for k, u in enumerate(syl.coda):
            part = _consonant_ipa(index_of[id(u)], units, word)
            is_last = k == len(syl.coda) - 1
            can_carry = n + 1 < len(syllables) and not syllables[n + 1].onset
            if u.split is not None and is_last and can_carry:
                out += u.split[0]
                carry = u.split[1]
            else:
                out += part
        mark = "ˈ" if multi and stress == n else ""
        pieces.append(mark + out)
    return ".".join(pieces)


def analyze(word: str, lexicon: Lexicon | None = None) -> WordPhonology:
    """Analyse one word: syllable structure, final -e, IPA."""
    lex = merge(lexicon)
    norm = normalize(word)
    entry: LexEntry | None = lex.get(norm)
    units = tokenize(norm)
    syllables = syllabify(units)
    stress = assign_stress(syllables)
    rule_final_e = bool(units) and units[-1].final_e
    rule_core = len(syllables) - (1 if rule_final_e else 0)
    rule_ipa = _render(units, syllables, norm, stress) if syllables else norm
    last_schwa = bool(syllables) and syllables[-1].schwa
    if entry is None:
        return WordPhonology(norm, rule_ipa, rule_core, rule_final_e, last_schwa)
    core = entry.core if entry.core is not None else rule_core
    final_e = entry.final_e if entry.final_e is not None else rule_final_e
    ipa = entry.ipa if entry.ipa is not None else rule_ipa
    ends_schwa = final_e or last_schwa
    return WordPhonology(norm, ipa, core, final_e, ends_schwa, from_lexicon=True)


def transcribe(word: str, lexicon: Lexicon | None = None) -> str:
    """IPA for one word."""
    return analyze(word, lexicon).ipa


def transcribe_text(text: str, lexicon: Lexicon | None = None) -> list[tuple[str, str]]:
    """Transcribe every word of ``text``; returns ``(spelling, ipa)`` pairs."""
    pairs = []
    for raw in re.findall(r"[A-Za-zþðȝæÞÐȜÆ]+", text):
        pairs.append((raw, transcribe(raw, lexicon)))
    return pairs
