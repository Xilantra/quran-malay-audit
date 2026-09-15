"""Input parsing, Quran key validation, and source-aware comparison."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# Canonical Hafs verse counts. This is structural metadata only, not a
# translation dump, and gives every local export the same deterministic key set.
SURAH_AYAH_COUNTS: Tuple[int, ...] = (
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
    128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
    34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35,
    38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11,
    11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40,
    46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8,
    8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6,
)
EXPECTED_VERSE_COUNT = sum(SURAH_AYAH_COUNTS)
VERSE_KEY_RE = re.compile(r"^(\d+):(\d+)$")


class ExportFormatError(ValueError):
    """Raised when a local JSON or SQLite export cannot be read."""


@dataclass(frozen=True)
class ExportRows:
    """Rows retained as a list so duplicate keys remain observable."""

    records: List[Tuple[str, str]]
    format: str


@dataclass(frozen=True)
class ValidationReport:
    source_key: Optional[str]
    input_path: str
    input_format: str
    record_count: int
    unique_key_count: int
    duplicates: List[str]
    missing: List[str]
    unexpected: List[str]
    empty_text: List[str]

    @property
    def is_valid(self) -> bool:
        return not (
            self.duplicates
            or self.missing
            or self.unexpected
            or self.empty_text
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_key": self.source_key,
            "input_path": self.input_path,
            "input_format": self.input_format,
            "expected_verse_count": EXPECTED_VERSE_COUNT,
            "record_count": self.record_count,
            "unique_key_count": self.unique_key_count,
            "duplicates": self.duplicates,
            "missing": self.missing,
            "unexpected": self.unexpected,
            "empty_text": self.empty_text,
            "is_valid": self.is_valid,
            "normalization": "not applied to source text; analysis-only normalization is available separately",
        }


def expected_verse_keys() -> List[str]:
    return [
        f"{surah}:{ayah}"
        for surah, count in enumerate(SURAH_AYAH_COUNTS, start=1)
        for ayah in range(1, count + 1)
    ]


def normalize_for_analysis(value: str) -> str:
    """Return a comparison key without changing any stored source text."""

    normalized = unicodedata.normalize("NFKC", value).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _text_value(value: Any, context: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "t", "translation", "content", "value"):
            if isinstance(value.get(key), str):
                return value[key]
    raise ExportFormatError(f"{context} has no string translation text")


def _record_dict(record: Dict[str, Any], context: str) -> Tuple[str, str]:
    key: Any = None
    for candidate in ("verse_key", "ayah_key", "key"):
        if candidate in record:
            key = record[candidate]
            break
    if key is None:
        surah = record.get("surah", record.get("sura", record.get("surah_id")))
        ayah = record.get("ayah", record.get("ayah_number"))
        if surah is not None and ayah is not None:
            key = f"{surah}:{ayah}"
    if key is None:
        raise ExportFormatError(f"{context} has no verse key")

    text: Any = None
    for candidate in ("text", "t", "translation", "content", "value"):
        if candidate in record:
            text = record[candidate]
            break
    if text is None:
        raise ExportFormatError(f"{context} has no translation text")
    return str(key), _text_value(text, context)


def _json_rows(data: Any) -> ExportRows:
    if isinstance(data, dict):
        for container_key in ("translations", "data", "records", "items"):
            if isinstance(data.get(container_key), list):
                rows = [
                    _record_dict(record, f"{container_key}[{index}]")
                    for index, record in enumerate(data[container_key])
                ]
                return ExportRows(rows, "json-records")

        if data and all(VERSE_KEY_RE.match(str(key)) for key in data):
            rows = [
                (str(key), _text_value(value, f"key {key!r}"))
                for key, value in data.items()
            ]
            return ExportRows(rows, "json-key-value")

        raise ExportFormatError(
            "JSON must be a verse-key object, a list of records, or contain a translations list"
        )

    if isinstance(data, list):
        if all(isinstance(item, dict) for item in data):
            rows = [
                _record_dict(record, f"records[{index}]")
                for index, record in enumerate(data)
            ]
            return ExportRows(rows, "json-records")

        if all(isinstance(item, list) for item in data):
            rows: List[Tuple[str, str]] = []
            for surah, ayahs in enumerate(data, start=1):
                for ayah, value in enumerate(ayahs, start=1):
                    rows.append((f"{surah}:{ayah}", _text_value(value, f"[{surah - 1}][{ayah - 1}]")))
            return ExportRows(rows, "json-nested-arrays")

    raise ExportFormatError("Unsupported JSON export structure")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_rows(path: Path) -> ExportRows:
    with sqlite3.connect(str(path)) as database:
        tables = [
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            columns = [row[1] for row in database.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            )]
            lowered = {column.lower(): column for column in columns}
            key_column = next(
                (lowered[name] for name in ("verse_key", "ayah_key", "key") if name in lowered),
                None,
            )
            text_column = next(
                (
                    lowered[name]
                    for name in ("text", "translation", "content", "value")
                    if name in lowered
                ),
                None,
            )
            derived_key = False
            if key_column is None:
                surah_column = next(
                    (lowered[name] for name in ("surah", "sura", "surah_id") if name in lowered),
                    None,
                )
                ayah_column = next(
                    (lowered[name] for name in ("ayah", "ayah_number") if name in lowered),
                    None,
                )
                if surah_column is not None and ayah_column is not None:
                    key_column = (surah_column, ayah_column)
                    derived_key = True
            if key_column is None or text_column is None:
                continue

            if derived_key:
                select = (
                    f"SELECT {_quote_identifier(key_column[0])}, {_quote_identifier(key_column[1])}, "
                    f"{_quote_identifier(text_column)} FROM {_quote_identifier(table)}"
                )
                records = [
                    (f"{row[0]}:{row[1]}", "" if row[2] is None else str(row[2]))
                    for row in database.execute(select)
                ]
            else:
                select = (
                    f"SELECT {_quote_identifier(key_column)}, {_quote_identifier(text_column)} "
                    f"FROM {_quote_identifier(table)}"
                )
                records = [
                    (str(row[0]), "" if row[1] is None else str(row[1]))
                    for row in database.execute(select)
                ]
            return ExportRows(records, "sqlite")

    raise ExportFormatError(
        f"No table with a verse-key/translation-text shape was found in {path}"
    )


def load_export_rows(path: Path) -> ExportRows:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        return _sqlite_rows(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ExportFormatError(f"Invalid JSON export {path}: {error}") from error
    return _json_rows(data)


def _key_sort(key: str) -> Tuple[int, int, str]:
    match = VERSE_KEY_RE.match(key)
    if match:
        return int(match.group(1)), int(match.group(2)), key
    return 10**9, 10**9, key


def validate_export(path: Path, source_key: Optional[str] = None) -> ValidationReport:
    rows = load_export_rows(path)
    keys = [key for key, _ in rows.records]
    counts = Counter(keys)
    expected = set(expected_verse_keys())
    actual = set(keys)
    duplicates = sorted(
        [key for key, count in counts.items() if count > 1],
        key=_key_sort,
    )
    missing = sorted(expected - actual, key=_key_sort)
    unexpected = sorted(actual - expected, key=_key_sort)
    empty_text = sorted(
        {key for key, text in rows.records if not text.strip()},
        key=_key_sort,
    )
    return ValidationReport(
        source_key=source_key,
        input_path=str(path),
        input_format=rows.format,
        record_count=len(rows.records),
        unique_key_count=len(actual),
        duplicates=duplicates,
        missing=missing,
        unexpected=unexpected,
        empty_text=empty_text,
    )


def _first_value(rows: Iterable[Tuple[str, str]]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for key, text in rows:
        values.setdefault(key, text)
    return values


def compare_exports(
    left_path: Path,
    right_path: Path,
    left_source_key: str,
    right_source_key: str,
) -> List[Dict[str, Any]]:
    left = _first_value(load_export_rows(left_path).records)
    right = _first_value(load_export_rows(right_path).records)
    differences: List[Dict[str, Any]] = []
    all_keys = sorted(set(left) | set(right), key=_key_sort)

    for verse_key in all_keys:
        observed = left.get(verse_key)
        proposed = right.get(verse_key)
        if observed == proposed:
            continue
        if observed is None or proposed is None:
            difference_type = "missing-in-one-source"
        elif normalize_for_analysis(observed) == normalize_for_analysis(proposed):
            difference_type = "format"
        else:
            difference_type = "candidate-spelling-or-wording"
        differences.append(
            {
                "source_key": left_source_key,
                "comparison_source_key": right_source_key,
                "verse_key": verse_key,
                "status": "candidate",
                "difference_type": difference_type,
                "observed": observed,
                "proposed": proposed,
                "evidence": "Cross-source difference only; requires independent editorial review.",
                "reviewer": None,
                "upstream_ticket": None,
                "is_error": False,
            }
        )
    return differences
