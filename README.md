# chaucer

**Scope.** Middle English scansion, transcription and reading of Chaucer's Canterbury Tales: a
phonological transcriber, a final -e scansion validator, corpus ingestion of Skeat's General
Prologue, and HTML report and practice-sheet renderers. It is not the owner's handwriting and
script-learning project (that is `4444J99/hand-script`) and not vers.forms, the owner's poetry
studio (`4444J99/journal-handwritten-web`, `4444J99/versforms`). Private.

History: this repository was `hand-script` until 2026-11-15, when the Chaucer work and the
handwriting project were separated; its commits and PRs 1-8 are the Chaucer work and keep their
history here. The Perplexity Space named in the manifest began as a handwriting and linguistics
curriculum and moved to Middle English on 2026-11-10; only the Middle English half lives here.

## What is here

| Component | Module | Status |
|-----------|--------|--------|
| Phonological transcriber (Chaucerian ME to syllabified IPA) | `chaucer.middle_english.phonology` | implemented |
| Final -e scansion validator | `chaucer.middle_english.scansion` | implemented |
| Source-thread manifest | `chaucer.manifest`, `src/chaucer/data/project_manifest.json` | implemented |
| Corpus ingestion (validator over a verse file, JSON report) | `chaucer.corpus` | implemented |
| Corpus report as HTML (verdicts and final -e marked per word) | `chaucer.render` | implemented |
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
chaucer scan "Whan that Aprille with his shoures soote"
chaucer transcribe "nyght sweete"
chaucer manifest --check
chaucer ingest-corpus corpus/chaucer_gp_skeat.txt -o corpus/chaucer_gp_skeat.report.json
chaucer triage-corpus corpus/chaucer_gp_skeat.txt -o corpus/chaucer_gp_skeat.triage.json
chaucer render-report corpus/chaucer_gp_skeat.report.json -o corpus/chaucer_gp_skeat.report.html
chaucer check-fixtures tests/fixtures/gp_opening.json   # add lines, get pass/fail
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

## Verification status

Hosted `ci` runs on this repository die in about 3 seconds with zero steps (for example run 43604399103 on `c28b15e`): nothing executes, so a red hosted check means only that hosted checks cannot start. It is not a code result, and a dead check is not a pass.

The `.github/workflows/ci.yml` commands are run locally from a fresh clone. Local-green record, base `c28b15ed1c76f3f783ba9409ee2e9a2c3379b632` (2026-11-14), each in a fresh venv with `pip install -e ".[dev]"` (ruff 0.17.5):

- Python 3.11 and 3.13: `ruff check .` pass; `ruff format --check .` pass (14 files); `pytest` pass, 111 tests each
- Python 3.12, the third matrix entry, is not installed on this machine and was not run

### Report page

`render-report REPORT.json` writes one self-contained HTML page (no scripts, no network, no
timestamps): the pass rate, a syllables-per-line histogram, and every verse line with its
verdict. In each line a final -e is marked by what the validator did with it: counted, elided
before a vowel or weak h (struck through), or kept at the line end. The report supplies the
verdicts; each line is re-scanned only for the per-word -e behaviour and must reproduce the
report's syllable count, so a report made with `--lexicon` needs the same `--lexicon` here.
`corpus/chaucer_gp_skeat.report.html` is the page for the committed report (open it in a browser;
the pass/fail filter is CSS only); a test checks it equals a fresh render.

### Corpus pass rate and triage

`corpus/chaucer_gp_skeat.txt` is Skeat's General Prologue (860 lines). The committed report
records the validator's verdict per line (631/860 pass, 73.37%) and the manifest carries the
same totals; tests fail if either drifts. Source threads record `ingest` with 0 lines and a
reason because their bodies are not locally recoverable, so there is no per-thread pass rate.

`triage-corpus` asks, for each word in a failing line, how many corpus lines would flip if the
lexicon dropped its final -e or one syllable (net of lines it would break). It ranks evidence for
the next lexicon entries; the validator is the oracle, so a candidate still needs checking
against the edition before it is added. The first candidate in the committed triage is `were`
as one syllable (12 lines fixed, 0 broken).

## Owner decisions open

- **LICENSE**: not chosen. No license file is shipped and `pyproject.toml` declares
  "Proprietary - owner decision pending"; until the owner picks one, all rights are reserved.
- Whether the repository stays private.
