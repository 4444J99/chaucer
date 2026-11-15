"""Exceptions lexicon for the rule-based Middle English engine.

The orthography-driven rules in :mod:`chaucer.middle_english.phonology`
cover the regular cases. Anything the spelling cannot determine (syncope,
French stress, borrowed consonant clusters, homographs) is recorded here as an
explicit, inspectable entry rather than hidden in the rules.

Entries are keyed by the normalised (lower-case) spelling used by Riverside-style
editions of Chaucer. Callers may pass their own entries to override these.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LexEntry:
    """One irregular word.

    ``core`` is the number of syllables *excluding* a final -e syllable and
    ``final_e`` says whether the word carries an elidable final -e syllable
    after those. ``None`` means "derive that part from the spelling rules".
    ``ipa`` is the full transcription with ``.`` syllable breaks and ``ˈ``
    stress, or ``None`` to derive it.
    """

    ipa: str | None = None
    core: int | None = None
    final_e: bool | None = None


Lexicon = dict[str, LexEntry]

DEFAULT_LEXICON: Lexicon = {
    # Function words: the spelling alone cannot tell schwa from long vowel.
    "the": LexEntry(ipa="ðə"),
    "he": LexEntry(ipa="heː"),
    "me": LexEntry(ipa="meː"),
    "we": LexEntry(ipa="weː"),
    "she": LexEntry(ipa="ʃeː"),
    "thee": LexEntry(ipa="ðeː"),
    "so": LexEntry(ipa="soː"),
    "to": LexEntry(ipa="toː"),
    "of": LexEntry(ipa="ɔv"),
    # Syncope: an unstressed medial vowel that the spelling keeps but the
    # verse does not count.
    "every": LexEntry(ipa="ˈɛv.rɪ", core=2, final_e=False),
    "foweles": LexEntry(ipa="ˈfuː.ləs", core=2, final_e=False),
    # French loans with final stress, or clusters the rules would misread.
    "aprille": LexEntry(ipa="a.ˈprɪl.lə", core=2, final_e=True),
    "vertu": LexEntry(ipa="vɛr.ˈtyː", core=2, final_e=False),
    "licour": LexEntry(ipa="lɪ.ˈkuːr", core=2, final_e=False),
    "engendred": LexEntry(ipa="ɛn.ˈdʒɛn.drəd", core=3, final_e=False),
    "melodye": LexEntry(ipa="mɛ.lɔ.ˈdiː.ə", core=3, final_e=True),
    "yonge": LexEntry(ipa="ˈjʊŋ.gə", core=1, final_e=True),
    "zephirus": LexEntry(ipa="ˈzɛ.fɪ.rʊs", core=3, final_e=False),
}


def merge(extra: Lexicon | None) -> Lexicon:
    """Return the default lexicon updated with caller-supplied entries."""
    if not extra:
        return DEFAULT_LEXICON
    merged = dict(DEFAULT_LEXICON)
    merged.update({k.lower(): v for k, v in extra.items()})
    return merged


def entries_from_json(data: dict[str, dict[str, object]]) -> Lexicon:
    """Build a lexicon from a JSON-style mapping (used by fixtures and the CLI)."""
    out: Lexicon = {}
    for word, spec in data.items():
        unknown = set(spec) - {"ipa", "core", "final_e"}
        if unknown:
            raise ValueError(f"lexicon entry {word!r} has unknown keys {sorted(unknown)}")
        ipa = spec.get("ipa")
        core = spec.get("core")
        final_e = spec.get("final_e")
        out[word.lower()] = LexEntry(
            ipa=None if ipa is None else str(ipa),
            core=None if core is None else int(core),  # type: ignore[call-overload]
            final_e=None if final_e is None else bool(final_e),
        )
    return out
