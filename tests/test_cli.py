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
