"""Handwriting practice sheet: selection, ruled rows, escaping, CLI, and the committed page."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chaucer import corpus, practice
from chaucer.cli import main
from chaucer.render import RenderError

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "corpus" / "chaucer_gp_skeat.txt"
PAGE = ROOT / "corpus" / "chaucer_gp_skeat.practice.html"


def _lines():
    return corpus.parse_corpus(CORPUS.read_bytes(), CORPUS.stem)


def _sheet(start="GP.1", count=12, per_page=3, lexicon=None):
    chosen = practice.select_lines(_lines(), start, count)
    return practice.render_sheet(chosen, CORPUS.name, lexicon, per_page)


def test_select_lines_defaults_and_ranges():
    lines = _lines()
    assert practice.select_lines(lines, None, 2) == lines[:2]
    picked = practice.select_lines(lines, "GP.5", 3)
    assert [ln.ref for ln in picked] == ["GP.5", "GP.6", "GP.7"]


@pytest.mark.parametrize(
    ("start", "count", "message"),
    [
        ("GP.99999", 1, "unknown reference"),
        ("GP.1", 0, "at least 1"),
        (_lines()[-3].ref, 50, "only"),
    ],
)
def test_select_lines_rejects_bad_requests(start, count, message):
    with pytest.raises(RenderError, match=message):
        practice.select_lines(_lines(), start, count)


def test_each_line_gets_one_trace_row_and_two_empty_rows():
    page = _sheet(count=4)
    assert page.count('<section class="block">') == 4
    assert page.count('<svg class="row"') == 12
    assert page.count("<text ") == 4  # one tracing model per line, empty rows carry none


def test_guides_are_ruled_and_trace_text_sits_on_the_baseline():
    page = _sheet(count=1)
    row = re.search(r'<svg class="row".*?</svg>', page, re.S)
    assert row is not None
    assert row.group(0).count("<line ") == 4
    assert f'y1="{practice.BASELINE}"' in row.group(0)
    assert f'<text x="10" y="{practice.BASELINE}"' in row.group(0)


def test_pages_break_every_per_page_lines():
    page = _sheet(count=7, per_page=3)
    assert page.count('<div class="page">') == 3
    blocks = [seg.count('<section class="block">') for seg in page.split('<div class="page">')[1:]]
    assert blocks == [3, 3, 1]


def test_long_lines_shrink_the_trace_font_to_fit():
    long_text = "x" * 50
    row = practice._row_svg(long_text)
    size = float(re.search(r'font-size="([\d.]+)"', row).group(1))
    assert size < practice.MAX_FONT
    assert size * practice.CHAR_WIDTH * 50 <= practice.ROW_WIDTH
    short = practice._row_svg("a")
    assert f'font-size="{practice.MAX_FONT}"' in short


def test_model_line_marks_final_e_and_shows_scansion_and_ipa():
    page = _sheet(count=1)
    assert 'class="e-lineend"' in page
    assert "11 syllables" in page
    assert "ok feminine" in page
    assert "ˈʃuː.rəs" in page


def test_failing_line_is_flagged_not_hidden():
    lines = [corpus.CorpusLine("T.1", "Short line")]
    page = practice.render_sheet(lines, "t.txt")
    assert "scansion fails" in page
    assert "Short line" in page


def test_text_is_escaped_in_model_and_trace():
    lines = [corpus.CorpusLine("T.1<", "A <b>bold</b> & line")]
    page = practice.render_sheet(lines, "<t>.txt")
    assert "<b>bold" not in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page
    assert "<t>" not in page


def test_page_is_self_contained_deterministic_and_prints_white():
    one = _sheet()
    assert one == _sheet()
    assert "<script" not in one
    assert "https://" not in one
    assert "@page { size: A4" in one
    assert "background: #fff" in one


def test_render_sheet_rejects_empty_and_bad_per_page():
    with pytest.raises(RenderError, match="no lines"):
        practice.render_sheet([], "t.txt")
    with pytest.raises(RenderError, match="per-page"):
        practice.render_sheet(_lines()[:1], "t.txt", per_page=0)


def test_committed_page_reproduces():
    assert PAGE.read_text("utf-8") == _sheet(start="GP.1", count=12, per_page=3)


def test_cli_writes_the_committed_page(tmp_path):
    out = tmp_path / "s.html"
    assert (
        main(["practice-sheet", str(CORPUS), "--start", "GP.1", "--count", "12", "-o", str(out)])
        == 0
    )
    assert out.read_text("utf-8") == PAGE.read_text("utf-8")


def test_cli_prints_to_stdout_without_output(capsys):
    assert main(["practice-sheet", str(CORPUS), "--count", "2"]) == 0
    assert capsys.readouterr().out == _sheet(count=2)


@pytest.mark.parametrize(
    "argv",
    [
        ["--start", "NOPE"],
        ["--count", "0"],
        ["--per-page", "0"],
        ["--count", "9999"],
    ],
)
def test_cli_errors_exit_2_without_traceback(argv, capsys):
    assert main(["practice-sheet", str(CORPUS), *argv]) == 2
    err = capsys.readouterr().err
    assert err.startswith("practice-sheet:")
    assert "Traceback" not in err


def test_cli_missing_file_bad_corpus_and_unwritable_output(tmp_path, capsys):
    assert main(["practice-sheet", str(tmp_path / "none.txt")]) == 2
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing\n", "utf-8")
    assert main(["practice-sheet", str(empty)]) == 2
    assert main(["practice-sheet", str(CORPUS), "-o", str(tmp_path / "no" / "x.html")]) == 2
    assert "Traceback" not in capsys.readouterr().err
