"""Project manifest of the Perplexity source threads behind chaucer."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA = "chaucer.manifest/1"
LINEAGE_ID = re.compile(r"^perplexity-[0-9a-f]{8}$")
CORPUS_KEYS = ("id", "file", "work", "edition", "rights", "url", "retrieved")
STATUSES = frozenset({"implemented", "not started"})


class ManifestError(ValueError):
    """Raised when a manifest fails validation."""


@dataclass(frozen=True)
class Manifest:
    data: dict[str, Any]

    @property
    def space_id(self) -> str:
        return str(self.data["space"]["id"])

    @property
    def thread_ids(self) -> list[str]:
        return [t["id"] for t in self.data["threads"]]

    @property
    def followup_ids(self) -> list[str]:
        return [t["id"] for t in self.data["computer_followups"]]

    @property
    def lineage_ids(self) -> list[str]:
        return [t["id"] for t in self.data["lineage"]]

    @property
    def all_source_ids(self) -> list[str]:
        return [self.space_id, *self.thread_ids, *self.followup_ids, *self.lineage_ids]


def _check_uuid(value: object, where: str) -> None:
    try:
        parsed = uuid.UUID(str(value))
    except ValueError as exc:
        raise ManifestError(f"{where}: {value!r} is not a UUID") from exc
    if str(parsed) != str(value):
        raise ManifestError(f"{where}: {value!r} is not in canonical lower-case UUID form")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_rate(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1


def _check_result(result: object, where: str) -> None:
    """A corpus ``result`` block: counts and a pass rate that agree with each other."""
    if not isinstance(result, dict):
        raise ManifestError(f"{where} is required and must be an object")
    for key in ("total", "passed", "failed"):
        if not _is_int(result.get(key)) or result[key] < 0:
            raise ManifestError(f"{where}.{key} must be a non-negative integer")
    if result["passed"] + result["failed"] != result["total"]:
        raise ManifestError(f"{where}: passed + failed must equal total")
    if not _is_rate(result.get("pass_rate")):
        raise ManifestError(f"{where}.pass_rate must be a number between 0 and 1")
    if result["total"] and result["pass_rate"] != round(result["passed"] / result["total"], 4):
        raise ManifestError(f"{where}.pass_rate disagrees with passed/total")


def _check_ingest(ingest: object, where: str, corpus_ids: set[str], data: dict[str, Any]) -> None:
    """A thread ``ingest`` record: honest zero-line null, or a real corpus attribution."""
    if not isinstance(ingest, dict):
        raise ManifestError(f"{where} record is required and must be an object")
    lines = ingest.get("lines")
    if not _is_int(lines) or lines < 0:
        raise ManifestError(f"{where}.lines must be a non-negative integer")
    if lines == 0:
        if ingest.get("pass_rate") is not None or not ingest.get("reason"):
            raise ManifestError(f"{where}: zero lines need pass_rate null and a reason")
        if ingest.get("corpus_id") is not None:
            raise ManifestError(f"{where}: zero lines cannot name a corpus_id")
        return
    corpus_id = ingest.get("corpus_id")
    if not isinstance(corpus_id, str) or corpus_id not in corpus_ids:
        raise ManifestError(f"{where}.corpus_id names no corpus")
    if not _is_rate(ingest.get("pass_rate")):
        raise ManifestError(f"{where}.pass_rate must be a number between 0 and 1")
    corpus = next(c for c in data["corpora"] if c.get("id") == corpus_id)
    if lines > corpus["result"]["total"]:
        raise ManifestError(f"{where}.lines exceeds the corpus total")


def validate(data: dict[str, Any]) -> Manifest:
    """Validate a manifest mapping and return it wrapped; raise :class:`ManifestError`."""
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")
    if data.get("schema") != SCHEMA:
        raise ManifestError(f"schema must be {SCHEMA!r}, got {data.get('schema')!r}")
    for key in ("project", "space", "threads", "computer_followups", "lineage", "components"):
        if key not in data:
            raise ManifestError(f"missing key {key!r}")
    if not isinstance(data["project"], str):
        raise ManifestError("project must be a string")
    if not isinstance(data["space"], dict):
        raise ManifestError("space must be an object")
    sections = ["threads", "computer_followups", "lineage", "components"]
    if "corpora" in data:
        sections.append("corpora")
    for section in sections:
        items = data[section]
        if not isinstance(items, list):
            raise ManifestError(f"{section} must be an array")
        for n, item in enumerate(items):
            if not isinstance(item, dict):
                raise ManifestError(f"{section}[{n}] must be an object")
    _check_uuid(data["space"].get("id"), "space.id")
    for section in ("threads", "computer_followups"):
        for n, item in enumerate(data[section]):
            _check_uuid(item.get("id"), f"{section}[{n}].id")
    for n, item in enumerate(data["lineage"]):
        if not LINEAGE_ID.match(str(item.get("id"))):
            raise ManifestError(f"lineage[{n}].id {item.get('id')!r} is not perplexity-<8 hex>")
    for n, corpus in enumerate(data.get("corpora", [])):
        missing = [k for k in CORPUS_KEYS if not corpus.get(k)]
        if missing:
            raise ManifestError(f"corpora[{n}] missing {missing}")
        if not isinstance(corpus["id"], str):
            raise ManifestError(f"corpora[{n}].id must be a string")
        _check_result(corpus.get("result"), f"corpora[{n}].result")
    corpus_ids = [c["id"] for c in data.get("corpora", [])]
    dup_corpora = sorted({i for i in corpus_ids if corpus_ids.count(i) > 1})
    if dup_corpora:
        raise ManifestError(f"duplicate corpus ids: {dup_corpora}")
    for n, thread in enumerate(data["threads"]):
        _check_ingest(thread.get("ingest"), f"threads[{n}].ingest", corpus_ids, data)
    manifest = Manifest(data)
    ids = manifest.all_source_ids
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ManifestError(f"duplicate ids: {dupes}")
    for n, comp in enumerate(data["components"]):
        if comp.get("status") not in STATUSES:
            raise ManifestError(f"components[{n}].status must be one of {sorted(STATUSES)}")
        if (comp.get("status") == "implemented") != bool(comp.get("module")):
            raise ManifestError(f"components[{n}]: module is set exactly when implemented")
    return manifest


def load(path: Path | None = None) -> Manifest:
    """Load and validate a manifest (the packaged one by default)."""
    if path is None:
        text = resources.files("chaucer").joinpath("data/project_manifest.json").read_text("utf-8")
    else:
        text = Path(path).read_text("utf-8")
    return validate(json.loads(text))
