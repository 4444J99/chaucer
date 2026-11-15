"""Counterfactual corpus triage: ranking, determinism, CLI, and the committed output."""

from __future__ import annotations

import json
from pathlib import Path

from chaucer import corpus, triage
from chaucer.cli import main

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "chaucer_gp_skeat.txt"
TRIAGE = ROOT / "corpus" / "chaucer_gp_skeat.triage.json"
REPORT = ROOT / "corpus" / "chaucer_gp_skeat.report.json"

# "were" counted with a pronounced final -e makes this line 11 syllables ending on "See"
WERE_LINE = b"G.1\tWhan they were wonne; and in the Grete See\n"


def test_no_final_e_for_were_fixes_the_line_and_breaks_nothing():
    result = triage.triage(WERE_LINE, "x.txt", "x")
    were = next(c for c in result["candidates"] if c["word"] == "were")
    assert (were["variant"], were["fixed"], were["broken"], were["gain"]) == ("no_final_e", 1, 0, 1)
    assert were["fixed_refs"] == ["G.1"]
    assert result["baseline"] == {"total": 1, "passed": 0, "failed": 1}


def test_a_passing_corpus_has_no_candidates():
    data = b"A.1\tWhan that Aprille with his shoures soote\n"
    result = triage.triage(data, "x.txt", "x")
    assert result["baseline"]["failed"] == 0
    assert result["candidates"] == []


def test_gain_counts_lines_broken_as_well_as_fixed():
    # "hadde" without its final -e fixes the first line but breaks the second
    data = b"A.1\tAnd he hadde seyn the world so wyde\nA.2\tHe hadde a berd as brood as any spade\n"
    result = triage.triage(data, "x.txt", "x")
    for cand in result["candidates"]:
        assert cand["gain"] == cand["fixed"] - cand["broken"]


def test_output_is_deterministic_and_respects_top():
    one = triage.triage(CORPUS.read_bytes(), CORPUS.name, CORPUS.stem, top=5)
    two = triage.triage(CORPUS.read_bytes(), CORPUS.name, CORPUS.stem, top=5)
    assert corpus.dumps(one) == corpus.dumps(two)
    assert len(one["candidates"]) == 5
    assert one["candidates_considered"] > 5


def test_candidates_are_sorted_by_gain_descending():
    result = json.loads(TRIAGE.read_text("utf-8"))
    gains = [c["gain"] for c in result["candidates"]]
    assert gains == sorted(gains, reverse=True)


def test_committed_triage_reproduces_and_agrees_with_the_report():
    expected = corpus.dumps(triage.triage(CORPUS.read_bytes(), CORPUS.name, CORPUS.stem))
    assert TRIAGE.read_text("utf-8") == expected
    summary = json.loads(REPORT.read_text("utf-8"))["summary"]
    base = json.loads(TRIAGE.read_text("utf-8"))["baseline"]
    assert (base["total"], base["passed"], base["failed"]) == (
        summary["total"],
        summary["passed"],
        summary["failed"],
    )


def test_cli_writes_triage_and_reports_counts(tmp_path, capsys):
    src = tmp_path / "v.txt"
    src.write_bytes(WERE_LINE)
    out = tmp_path / "t.json"
    assert main(["triage-corpus", str(src), "-o", str(out), "--top", "3"]) == 0
    assert "1 failing lines" in capsys.readouterr().err
    assert json.loads(out.read_text("utf-8"))["schema"] == triage.SCHEMA


def test_cli_reports_unreadable_and_empty_input(tmp_path, capsys):
    assert main(["triage-corpus", str(tmp_path / "missing.txt")]) == 2
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing\n", "utf-8")
    assert main(["triage-corpus", str(empty)]) == 2
    assert capsys.readouterr().err.count("triage-corpus:") == 2


def test_variant_keeps_the_existing_entry_ipa():
    from chaucer.middle_english.lexicon import DEFAULT_LEXICON

    entry = triage._variant_entry("every", DEFAULT_LEXICON, "syncope")
    assert entry is not None and entry.ipa == DEFAULT_LEXICON["every"].ipa


def test_cli_rejects_non_positive_top(tmp_path, capsys):
    src = tmp_path / "v.txt"
    src.write_bytes(WERE_LINE)
    assert main(["triage-corpus", str(src), "--top", "0"]) == 2
    assert "--top" in capsys.readouterr().err
