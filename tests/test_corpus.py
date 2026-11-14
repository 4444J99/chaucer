"""Corpus ingestion: parsing, report shape, determinism, CLI, and the committed report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hand_script import corpus, manifest
from hand_script.cli import main

ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "gp_opening.json"
CORPUS = ROOT / "corpus" / "chaucer_gp_skeat.txt"
REPORT = ROOT / "corpus" / "chaucer_gp_skeat.report.json"


def _fixture_corpus() -> bytes:
    cases = json.loads(FIXTURE.read_text("utf-8"))["lines"]
    return "\n".join(f"GP.{c['n']}\t{c['text']}" for c in cases).encode("utf-8")


def test_parse_skips_comments_and_blanks_and_numbers_bare_rows():
    lines = corpus.parse_corpus(b"# note\n\nA.1\tfirst line\nbare line\n", stem="demo")
    assert [(ln.ref, ln.text) for ln in lines] == [("A.1", "first line"), ("demo:4", "bare line")]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"# only a comment\n", "no verse lines"),
        (b"x\tone\nx\ttwo\n", "duplicate reference"),
        (b"\tno ref\n", "empty reference"),
        (b"ref\t\n", "empty reference"),
        ("caf\xe9".encode("latin-1"), "UTF-8"),
    ],
)
def test_parse_rejects_bad_input(data, message):
    with pytest.raises(corpus.CorpusError, match=message):
        corpus.parse_corpus(data)


def test_report_matches_validator_on_the_shipped_fixture():
    report = corpus.ingest(_fixture_corpus(), "gp.txt", "gp")
    # fixture line 10 needs a lexicon entry for "ye"; without it the validator sees 10 syllables
    by_ref = {r["ref"]: r for r in report["lines"]}
    assert by_ref["GP.1"] == {
        "ref": "GP.1",
        "text": "Whan that Aprille with his shoures soote",
        "ok": True,
        "kind": "feminine",
        "syllables": 11,
        "reasons": [],
    }
    assert by_ref["GP.10"]["syllables"] == 10
    assert all(r["ok"] for r in report["lines"])
    assert report["summary"] == {"total": 11, "passed": 11, "failed": 0, "pass_rate": 1.0}
    assert report["schema"] == corpus.SCHEMA
    assert report["source"]["sha256"] == hashlib.sha256(_fixture_corpus()).hexdigest()


def test_failures_are_recorded_with_the_validator_reason():
    data = b"A.1\tWhan that Aprille\nA.2\tAnd bathed every veyne in swich licour\n"
    report = corpus.ingest(data, "x.txt", "x")
    first, second = report["lines"]
    assert first["ok"] is False
    assert first["kind"] is None
    assert first["reasons"] == ["5 syllables; pentameter needs 10 or feminine 11"]
    assert second["ok"] is True
    assert report["summary"] == {"total": 2, "passed": 1, "failed": 1, "pass_rate": 0.5}


def test_lexicon_changes_the_result():
    data = b"G.10\tThat slepen al the nyght with open ye\n"
    plain = corpus.ingest(data, "x.txt", "x")
    assert plain["lines"][0]["syllables"] == 10
    from hand_script.middle_english import entries_from_json

    lex = entries_from_json({"ye": {"core": 1, "final_e": True, "ipa": "ˈiː.ə"}})
    with_lex = corpus.ingest(data, "x.txt", "x", lex)
    assert with_lex["lines"][0]["syllables"] == 11
    assert with_lex["lines"][0]["kind"] == "feminine"


def test_output_is_deterministic_and_has_no_timestamp():
    one = corpus.dumps(corpus.ingest(_fixture_corpus(), "gp.txt", "gp"))
    two = corpus.dumps(corpus.ingest(_fixture_corpus(), "gp.txt", "gp"))
    assert one == two
    assert json.loads(one)["source"].keys() == {"file", "sha256"}


def test_cli_writes_report_file_and_prints_rate(tmp_path, capsys):
    src = tmp_path / "v.txt"
    src.write_bytes(_fixture_corpus())
    out = tmp_path / "report.json"
    assert main(["ingest-corpus", str(src), "-o", str(out)]) == 0
    assert capsys.readouterr().err.strip() == "11/11 lines pass (100.00%)"
    assert json.loads(out.read_text("utf-8"))["summary"]["total"] == 11


def test_cli_stdout_report_is_json(tmp_path, capsys):
    src = tmp_path / "v.txt"
    src.write_text("Whan that Aprille\n", "utf-8")
    assert main(["ingest-corpus", str(src)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["lines"][0]["ref"] == "v:1"
    assert "0/1 lines pass (0.00%)" in captured.err


def test_cli_failures_do_not_change_exit_code_unless_threshold_set(tmp_path, capsys):
    src = tmp_path / "v.txt"
    src.write_text("Whan that Aprille\n", "utf-8")
    assert main(["ingest-corpus", str(src)]) == 0
    assert main(["ingest-corpus", str(src), "--min-pass-rate", "0.5"]) == 1
    assert "below --min-pass-rate" in capsys.readouterr().err


def test_cli_reports_unreadable_and_empty_input(tmp_path, capsys):
    assert main(["ingest-corpus", str(tmp_path / "missing.txt")]) == 2
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing\n", "utf-8")
    assert main(["ingest-corpus", str(empty)]) == 2
    assert capsys.readouterr().err.count("ingest-corpus:") == 2


def test_shipped_corpus_reproduces_the_committed_report():
    """The committed report is exactly what the current validator produces."""
    expected = corpus.dumps(corpus.ingest_file(CORPUS))
    assert REPORT.read_text("utf-8") == expected


def test_shipped_corpus_properties():
    report = json.loads(REPORT.read_text("utf-8"))
    summary = report["summary"]
    assert summary["total"] == 860  # 858 lines plus Skeat's bracketed 252 b, 252 c
    assert summary["passed"] + summary["failed"] == summary["total"]
    assert summary["pass_rate"] == round(summary["passed"] / summary["total"], 4)
    refs = [r["ref"] for r in report["lines"]]
    assert refs[0] == "GP.1" and "GP.858" in refs and "GP.252b" in refs
    assert report["lines"][0]["text"] == "Whan that Aprille with his shoures sote"


def test_manifest_records_the_corpus_source():
    entry = manifest.load().data["corpora"][0]
    assert entry["file"] == "corpus/chaucer_gp_skeat.txt"
    assert entry["retrieved"] == "2026-11-14"
    assert (
        entry["upstream_sha256"]
        == "2506000b31a78ae72dd9d1dd755fb3f305c42516b293960c222ad78509fc00db"
    )
    assert (ROOT / entry["file"]).exists() and (ROOT / entry["report"]).exists()


def test_manifest_rejects_corpus_entry_missing_fields():
    data = manifest.load().data
    data["corpora"] = [{"id": "x"}]
    with pytest.raises(manifest.ManifestError, match="corpora"):
        manifest.validate(data)
