# hand-script

Handwriting practice, etymology and Middle English tooling. The source is a Perplexity
Space (`053d129c-8941-4aa7-8dde-61aede81813d`) that began as a handwriting-practice and
linguistics curriculum (writing systems, etymological roots, 18 languages in nine
families) and on 2026-11-10 moved toward a Middle English corpus and generation pipeline.
This repository holds the tested code for that pipeline. Private.

## What is here

| Component | Module | Status |
|-----------|--------|--------|
| Phonological transcriber (Chaucerian ME to syllabified IPA) | `hand_script.middle_english.phonology` | implemented |
| Final -e scansion validator | `hand_script.middle_english.scansion` | implemented |
| Source-thread manifest | `hand_script.manifest`, `src/hand_script/data/project_manifest.json` | implemented |
| Corpus ingest, generation pipeline | | not started |

### Transcriber

Rule-based, driven by Riverside-style normalised spelling: digraphs (`ou` /uː/, `ee` /eː/),
`gh` as [x] or [ç] by the preceding vowel, `ng` as [ŋg], maximal-onset syllabification with
geminates split, vowel length from syllable shape, stress from lexicon, then prefix and
Romance-ending heuristics. Irregular words (syncope in `every`, French stress in `vertu`)
are explicit entries in `middle_english/lexicon.py`, flagged `from_lexicon` in the result.
It is a reconstruction aid, not a claim about any one manuscript.

### Final -e scansion validator

Rules, applied per line:

1. a final -e elides before a word beginning with a vowel (`droghte of`);
2. a final -e elides before `h` in weak function words (`he him his hir hem hath have hadde`...)
   and French silent-h words (`honour`, `honest`), not before other `h` (`hert`, `holt`);
3. a line-final -e is kept and gives the feminine ending;
4. the line must total 10 syllables, or 11 with a schwa-final last word.

It validates syllable count and final -e behaviour. It does not verify the stress pattern.
Only plain -e is elided; `-es -ed -en -eth` always count. Lines needing syncope or a homograph
choice take a lexicon entry (the General Prologue fixture does this for `ye`, "eye").

## Use

```sh
uv venv && uv pip install -e ".[dev]"
hand-script scan "Whan that Aprille with his shoures soote"
hand-script transcribe "nyght sweete"
hand-script manifest --check
pytest && ruff check . && ruff format --check .
```

Tests in `tests/` scan General Prologue lines 1-11 (`tests/fixtures/gp_opening.json`),
whose expected counts and final -e statuses were derived by hand before the engine ran.

## Owner decisions open

- **LICENSE**: not chosen. No license file is shipped and `pyproject.toml` declares
  "Proprietary - owner decision pending"; until the owner picks one, all rights are reserved.
- Whether the repository stays private.
