"""Manifest of the Perplexity source threads."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hand_script import manifest
from hand_script.cli import main

# Ids cited in the owner-goals file, domain 3.
GOALS_THREADS = {
    "0a7dad6d-8f2f-4c64-8b80-6279521a4194",
    "021ebcdc-1d87-4e2d-a339-e4d4e70ecc2a",
    "3b98b8a1-6241-4e0f-a7d8-877a2187cd0e",
    "4826f815-8947-41d6-9311-15a903f09d3f",
    "5e65736a-3dc6-4889-b78b-b741a0813280",
    "8731a6a7-2f3c-4faf-957c-48f14c3792ce",
    "1a777f46-6379-406e-99ac-f2c52c318db2",
}
GOALS_FOLLOWUPS = {
    "3662495e-fb0d-4192-b7bb-87bc4787685d",
    "ee67da89-8a05-440e-bd9e-fb6e6d926cea",
    "4417e674-ad3e-4cdf-9ffb-1ddbcff9bbc1",
}


def test_packaged_manifest_is_valid_and_complete():
    m = manifest.load()
    assert m.space_id == "053d129c-8941-4aa7-8dde-61aede81813d"
    assert set(m.thread_ids) == GOALS_THREADS
    assert set(m.followup_ids) == GOALS_FOLLOWUPS
    assert set(m.lineage_ids) == {
        "perplexity-8cd6edba",
        "perplexity-ed9afb35",
        "perplexity-2d71eed2",
        "perplexity-950fc2e4",
        "perplexity-a7afcc04",
    }
    assert len(m.all_source_ids) == 16


def test_implemented_components_resolve_to_real_modules():
    import importlib

    m = manifest.load()
    for comp in m.data["components"]:
        if comp["status"] == "implemented":
            importlib.import_module(comp["module"])


def _data():
    return copy.deepcopy(manifest.load().data)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(schema="x"), "schema"),
        (lambda d: d["space"].update(id="not-a-uuid"), "space.id"),
        (lambda d: d["threads"][0].update(id="0A7DAD6D-8F2F-4C64-8B80-6279521A4194"), "canonical"),
        (lambda d: d["threads"].append(dict(d["threads"][0])), "duplicate"),
        (lambda d: d["lineage"][0].update(id="perplexity-xyz"), "lineage"),
        (lambda d: d["components"][0].update(status="done"), "status"),
        (lambda d: d["components"][0].update(module=None), "module"),
        (lambda d: d.pop("threads"), "missing key"),
    ],
)
def test_invalid_manifests_are_rejected(mutate, message):
    data = _data()
    mutate(data)
    with pytest.raises(manifest.ManifestError, match=message):
        manifest.validate(data)


def test_cli_manifest_check(capsys):
    assert main(["manifest", "--check"]) == 0
    assert "manifest ok: 16 source ids" in capsys.readouterr().out


def test_cli_manifest_rejects_bad_file(tmp_path, capsys):
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"schema": "nope"}))
    assert main(["manifest", "--check", "--path", str(bad)]) == 1
    assert "invalid" in capsys.readouterr().err


def test_manifest_file_is_the_packaged_one():
    path = Path(manifest.__file__).parent / "data" / "project_manifest.json"
    assert json.loads(path.read_text("utf-8"))["project"] == "hand-script"
