"""Source-scoped, guarded correction loading and application."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Set, Tuple


ALLOWED_STATUSES = {"candidate", "confirmed", "rejected", "submitted", "fixed"}


class CorrectionManifestError(ValueError):
    """Raised when a correction manifest is incomplete or unsafe."""


class SourceMismatchError(CorrectionManifestError):
    """Raised when a correction manifest is used for another source track."""


def load_correction_manifest(path: Path) -> Dict[str, Any]:
    path = Path(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CorrectionManifestError(f"Invalid correction manifest {path}: {error}") from error
    if not isinstance(manifest, dict):
        raise CorrectionManifestError("Correction manifest must be an object")
    if manifest.get("version") != 1:
        raise CorrectionManifestError(
            f"Unsupported correction manifest version: {manifest.get('version')!r}"
        )
    if not isinstance(manifest.get("source_key"), str) or not manifest["source_key"]:
        raise CorrectionManifestError("Correction manifest must declare source_key")
    corrections = manifest.get("corrections")
    if not isinstance(corrections, list):
        raise CorrectionManifestError("Correction manifest must contain a corrections list")
    for index, correction in enumerate(corrections):
        if not isinstance(correction, dict):
            raise CorrectionManifestError(f"Correction {index} must be an object")
        required = {"verse_key", "find", "replace", "status"}
        if not required.issubset(correction):
            raise CorrectionManifestError(
                f"Correction {index} is missing {sorted(required - set(correction))}"
            )
        if not correction["find"] or correction["find"] == correction["replace"]:
            raise CorrectionManifestError(f"Invalid correction {index}: find/replace")
        if correction["status"] not in ALLOWED_STATUSES:
            raise CorrectionManifestError(
                f"Invalid correction status {correction['status']!r} at index {index}"
            )
        occurrences = correction.get("occurrences", 1)
        if not isinstance(occurrences, int) or occurrences < 1:
            raise CorrectionManifestError(f"Invalid occurrence count at index {index}")
    return manifest


def filter_corrections(
    manifest: Mapping[str, Any],
    source_key: str,
    statuses: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    if manifest.get("source_key") != source_key:
        raise SourceMismatchError(
            f"Manifest source {manifest.get('source_key')!r} does not match requested {source_key!r}"
        )
    allowed: Set[str] = set(statuses or {"confirmed"})
    if not allowed.issubset(ALLOWED_STATUSES):
        raise CorrectionManifestError(f"Unknown correction status filter: {sorted(allowed)}")
    return [
        correction
        for correction in manifest.get("corrections", [])
        if correction.get("status") in allowed
    ]


def _fragment_pattern(fragment: str) -> re.Pattern[str]:
    prefix = r"(?<!\w)" if fragment[0].isalnum() else ""
    suffix = r"(?!\w)" if fragment[-1].isalnum() else ""
    return re.compile(f"{prefix}{re.escape(fragment)}{suffix}")


def apply_corrections(
    texts: Mapping[str, str],
    manifest: Mapping[str, Any],
    source_key: str,
    statuses: Optional[Iterable[str]] = None,
) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Apply only source-matching approved records and return a new text map."""

    selected = filter_corrections(manifest, source_key, statuses=statuses)
    updated = dict(texts)
    applied = 0
    already_correct = 0

    for correction in selected:
        verse_key = correction["verse_key"]
        if verse_key not in updated:
            raise CorrectionManifestError(
                f"Approved correction verse {verse_key} is missing from the export"
            )
        expected_occurrences = correction.get("occurrences", 1)
        source_pattern = _fragment_pattern(correction["find"])
        replacement_pattern = _fragment_pattern(correction["replace"])
        source_text = updated[verse_key]
        source_count = len(source_pattern.findall(source_text))
        replacement_count = len(replacement_pattern.findall(source_text))
        if source_count == expected_occurrences:
            updated[verse_key] = source_pattern.sub(
                lambda _: correction["replace"], source_text
            )
            applied += 1
        elif source_count == 0 and replacement_count >= expected_occurrences:
            already_correct += 1
        else:
            raise CorrectionManifestError(
                "Correction precondition failed for "
                f"{verse_key}: expected {expected_occurrences} occurrence(s) of "
                f"{correction['find']!r}, found {source_count}"
            )

    return updated, {
        "considered": len(selected),
        "applied": applied,
        "already_correct": already_correct,
    }
