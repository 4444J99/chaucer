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
| Corpus ingestion (validator over a verse file, JSON report) | `hand_script.corpus` | implemented |
| Generation pipeline | | not started |

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
hand-script check-fixtures tests/fixtures/gp_opening.json   # add lines, get pass/fail
hand-script ingest-corpus corpus/chaucer_gp_skeat.txt -o /tmp/report.json
pytest && ruff check . && ruff format --check .
```

Tests in `tests/` scan General Prologue lines 1-11 (`tests/fixtures/gp_opening.json`),
whose expected counts and final -e statuses were derived by hand before the engine ran.

### Corpus ingestion

`ingest-corpus FILE` runs the validator, unchanged, over every verse line of `FILE`
(`ref<TAB>text` rows; `#` comments and blank rows skipped; a row without a tab is referenced
`<file stem>:<row>`). The JSON report holds, per line, `ref`, `text`, `ok`, `kind`, `syllables`
and `reasons`, plus `summary` (`total`, `passed`, `failed`, `pass_rate`) and the SHA-256 of the
input. Output is deterministic (no timestamps) and needs no network. Failures do not change the
exit code unless `--min-pass-rate` is given. `--lexicon` supplies extra lexicon entries.

`corpus/chaucer_gp_skeat.txt` is the General Prologue from Skeat's 1900 Oxford text (Project
Gutenberg #22120, via the GITenberg mirror); `corpus/chaucer_gp_skeat.report.json` is its run
report. Source, commit, checksum and retrieval date are in the manifest under `corpora`;
`scripts/extract_skeat_gp.py` regenerates the corpus file from the upstream text. A test checks
that the committed report equals a fresh run. Failing lines are data: the pass rate measures the
validator's rules against Skeat's spelling, not the quality of the verse, and the validator was
not tuned to this corpus.

## Owner decisions open

- **LICENSE**: not chosen. No license file is shipped and `pyproject.toml` declares
  "Proprietary - owner decision pending"; until the owner picks one, all rights are reserved.
- Whether the repository stays private.
