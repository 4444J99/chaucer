from __future__ import annotations

import json

from hand_script.cli import main


def test_scan_ok_line(capsys):
    assert main(["scan", "And bathed every veyne in swich licour"]) == 0
    out = capsys.readouterr().out
    assert "ok (masculine)" in out
    assert "veyne: elided_vowel" in out


def test_scan_failing_line_returns_nonzero(capsys):
    assert main(["scan", "Whan that Aprille"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_scan_with_lexicon_file(tmp_path, capsys):
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"ye": {"core": 1, "final_e": True, "ipa": "ˈiː.ə"}}))
    assert main(["scan", "--lexicon", str(lex), "That slepen al the nyght with open ye"]) == 0
    assert "ok (feminine)" in capsys.readouterr().out


def test_transcribe_prints_pairs(capsys):
    assert main(["transcribe", "nyght sweete"]) == 0
    assert capsys.readouterr().out.splitlines() == ["nyght\tnɪçt", "sweete\tˈsweː.tə"]


def test_check_fixtures_passes_on_the_shipped_fixture(capsys):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "gp_opening.json"
    assert main(["check-fixtures", str(fixture)]) == 0
    assert capsys.readouterr().out.strip().endswith(": ok")


def test_check_fixtures_reports_each_kind_of_mismatch(tmp_path, capsys):
    bad = {
        "lines": [
            {
                "n": 1,
                "text": "Whan that Aprille with his shoures soote",
                "syllables": 10,
                "kind": "masculine",
                "final_e": [["Aprille", "elided_vowel"]],
            }
        ]
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    assert main(["check-fixtures", str(path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "syllables 11 != 10" in out
    assert "kind 'feminine' != 'masculine'" in out
    assert "final -e" in out
