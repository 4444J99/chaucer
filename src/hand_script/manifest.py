"""Project manifest of the Perplexity source threads behind hand-script."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA = "hand-script.manifest/1"
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
        text = (
            resources.files("hand_script").joinpath("data/project_manifest.json").read_text("utf-8")
        )
    else:
        text = Path(path).read_text("utf-8")
    return validate(json.loads(text))
