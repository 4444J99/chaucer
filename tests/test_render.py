"""HTML rendering of a corpus report: final -e marking, faithful text, errors, committed page."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hand_script import corpus, render
from hand_script.cli import main
from hand_script.middle_english import entries_from_json, scan_line

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "chaucer_gp_skeat.txt"
REPORT = ROOT / "corpus" / "chaucer_gp_skeat.report.json"
PAGE = ROOT / "corpus" / "chaucer_gp_skeat.report.html"


def _line(text: str, lexicon=None) -> str:
    return render.line_html(text, scan_line(text, lexicon))


def test_pronounced_elided_and_line_end_e_are_marked():
    out = _line("The droghte of Marche hath perced to the rote,")
    assert 'droght<span class="e-elided" title="final -e elided before a vowel">e</span> of' in out
    assert 'March<span class="e-elided" title="final -e elided before weak h">e</span> hath' in out
    assert 'rot<span class="e-lineend" title="line-final -e kept">e</span>,' in out


def test_sounded_final_e_is_marked():
    out = _line("The tendre croppes, and the yonge sonne")
    assert 'tendr<span class="e-sounded" title="final -e counted">e</span> croppes' in out


def test_punctuation_and_spacing_are_kept_verbatim():
    text = "(So priketh hem nature in hir corages):"
    out = _line(text)
    assert out.startswith("(So priketh")
    assert out.endswith("corages):")
    assert "  " not in out


def test_hyphen_and_diaeresis_words_keep_their_text():
    out = _line("Hath in the Ram his halfe cours y-ronne,")
    assert "y-ronn" in out
    out = _line("That slepen al the night with open yë,")
    assert "yë" in out


def test_html_in_text_is_escaped():
    out = _line("Whan <b>that</b> Aprille & his shoures soote")
    assert "<b>" not in out
    assert "&amp;" in out


def test_lexicon_word_without_trailing_e_styles_the_whole_word():
    lexicon = entries_from_json({"fooa": {"ipa": "ˈfoːa", "final_e": True}})
    scan = scan_line("The fooa", lexicon)
    out = render.line_html("The fooa", scan)
    assert 'class="w-lineend"' in out


def test_text_word_count_mismatch_is_an_error():
    scan = scan_line("one two")
    with pytest.raises(render.RenderError, match="words in text"):
        render.line_html("one two three", scan)


def test_report_with_wrong_schema_is_rejected():
    with pytest.raises(render.RenderError, match="schema"):
        render.render_report({"schema": "nope"})


@pytest.mark.parametrize("bad", [[1, 2], None, "text"])
def test_non_object_report_is_rejected(bad):
    with pytest.raises(render.RenderError, match="schema"):
        render.render_report(bad)


def test_empty_report_is_rejected():
    report = json.loads(REPORT.read_text("utf-8"))
    report["lines"] = []
    report["summary"] = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}
    with pytest.raises(render.RenderError, match="no lines"):
        render.render_report(report)


def test_summary_that_contradicts_the_lines_is_rejected():
    report = json.loads(REPORT.read_text("utf-8"))
    report["summary"]["passed"] += 1
    with pytest.raises(render.RenderError, match="does not match"):
        render.render_report(report)


def _mini_report(rows):
    data = "\n".join(f"{ref}\t{text}" for ref, text in rows).encode("utf-8")
    return corpus.ingest(data, "mini.txt", "mini")


def test_all_pass_and_all_fail_reports_render():
    ok = render.render_report(_mini_report([("A.1", "Whan that Aprille with his shoures soote")]))
    assert "100.00%" in ok
    assert '<div class="line pass">' in ok
    assert '<div class="line fail">' not in ok
    bad = render.render_report(_mini_report([("A.1", "Short line")]))
    assert "0.00%" in bad
    assert '<div class="line fail">' in bad
    assert "pentameter needs 10 or feminine 11" in bad


def test_histogram_counts_match_the_report():
    report = json.loads(REPORT.read_text("utf-8"))
    page = render.render_report(report)
    for n in {r["syllables"] for r in report["lines"]}:
        count = sum(1 for r in report["lines"] if r["syllables"] == n)
        assert f'<span class="n">{n}</span>' in page
        assert f'<span class="c">{count}</span>' in page


def test_filter_markup_pairs_radios_with_line_states():
    page = render.render_report(json.loads(REPORT.read_text("utf-8")))
    for radio in ("f-all", "f-pass", "f-fail"):
        assert f'id="{radio}"' in page
        assert f'for="{radio}"' in page
    assert "#f-fail:checked ~ .lines .line.pass { display: none; }" in page


def test_report_fields_other_than_text_are_escaped():
    report = _mini_report([("A.1", "Whan that Aprille with his shoures soote")])
    report["lines"][0]["ref"] = '<i>"x"</i>'
    report["source"]["file"] = "<b>f</b>.txt"
    report["lines"][0]["kind"] = "<u>k</u>"
    page = render.render_report(report)
    for tag in ("<i>", "<b>f", "<u>"):
        assert tag not in page
    assert "&lt;b&gt;f&lt;/b&gt;.txt" in page


def test_lexicon_word_without_trailing_e_covers_sounded_and_elided():
    lexicon = entries_from_json({"fooa": {"ipa": "ˈfoːa", "core": 1, "final_e": True}})
    sounded = render.line_html("The fooa man", scan_line("The fooa man", lexicon))
    assert '<span class="w-sounded" title="final -e counted">fooa</span> man' in sounded
    elided = render.line_html("The fooa of", scan_line("The fooa of", lexicon))
    assert '<span class="w-elided"' in elided


def test_syllable_mismatch_with_report_is_an_error():
    report = json.loads(REPORT.read_text("utf-8"))
    report["lines"][0]["syllables"] += 1
    with pytest.raises(render.RenderError, match="re-scan gives"):
        render.render_report(report)


def test_page_is_self_contained_and_deterministic():
    report = json.loads(REPORT.read_text("utf-8"))
    one = render.render_report(report)
    assert one == render.render_report(report)
    assert "<script" not in one
    assert "http://" not in one.replace("http://www.w3.org", "")
    assert "https://" not in one
    assert one.count('<div class="line ') == len(report["lines"])


def test_committed_page_reproduces_from_the_committed_report():
    expected = render.render_report(json.loads(REPORT.read_text("utf-8")))
    assert PAGE.read_text("utf-8") == expected


def test_committed_report_is_still_current():
    fresh = corpus.dumps(corpus.ingest_file(CORPUS))
    assert REPORT.read_text("utf-8") == fresh


def test_cli_writes_the_page(tmp_path):
    out = tmp_path / "r.html"
    assert main(["render-report", str(REPORT), "-o", str(out)]) == 0
    assert out.read_text("utf-8") == PAGE.read_text("utf-8")


def test_cli_prints_to_stdout_without_output(capsys):
    assert main(["render-report", str(REPORT)]) == 0
    assert capsys.readouterr().out == PAGE.read_text("utf-8")


def test_cli_reports_an_unwritable_output_and_odd_reports(tmp_path, capsys):
    assert main(["render-report", str(REPORT), "-o", str(tmp_path / "no" / "x.html")]) == 2
    odd = tmp_path / "odd.json"
    for body in ("[1, 2]", "null", '{"schema": "hand-script.corpus-report/1", "lines": []}'):
        odd.write_text(body, "utf-8")
        assert main(["render-report", str(odd)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_cli_reports_a_missing_file(tmp_path, capsys):
    assert main(["render-report", str(tmp_path / "missing.json")]) == 2
    assert "render-report:" in capsys.readouterr().err


def test_cli_reports_bad_json_and_bad_schema(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{", "utf-8")
    assert main(["render-report", str(bad)]) == 2
    bad.write_text('{"schema": "x"}', "utf-8")
    assert main(["render-report", str(bad)]) == 2
    assert "schema" in capsys.readouterr().err


def test_cli_needs_the_lexicon_the_report_was_made_with(tmp_path, capsys):
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"were": {"ipa": "ˈwɛr", "final_e": False}}), "utf-8")
    report = corpus.ingest_file(CORPUS, entries_from_json(json.loads(lex.read_text("utf-8"))))
    rpath = tmp_path / "report.json"
    rpath.write_text(corpus.dumps(report), "utf-8")
    assert main(["render-report", str(rpath)]) == 2
    assert "re-scan gives" in capsys.readouterr().err
    assert main(["render-report", str(rpath), "--lexicon", str(lex)]) == 0
