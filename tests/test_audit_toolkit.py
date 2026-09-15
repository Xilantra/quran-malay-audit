import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from quran_ms_audit.core import (
    EXPECTED_VERSE_COUNT,
    compare_exports,
    expected_verse_keys,
    load_export_rows,
    normalize_for_analysis,
    validate_export,
)
from quran_ms_audit.corrections import (
    SourceMismatchError,
    apply_corrections,
    filter_corrections,
    load_correction_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "sources/registry.json"
FINDINGS_PATH = REPO_ROOT / "sources/quran.com/findings.json"
CORRECTIONS_PATH = REPO_ROOT / "sources/quran.com/corrections.json"
QUL_PATCH_PATH = REPO_ROOT / "sources/qul/resources/292-basamia/patch.json"


class AuditToolkitTests(unittest.TestCase):
    def test_registry_keeps_qurancom_and_qul_tracks_separate(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        sources = {source["source_key"]: source for source in registry["sources"]}

        self.assertEqual(sources["qurancom-ms-39"]["resource_id"], "39")
        self.assertEqual(sources["qul-ms-292"]["resource_id"], "292")
        self.assertEqual(sources["qul-130-metadata-anomaly"]["download_status"], "excluded")
        self.assertNotEqual(sources["qurancom-ms-39"]["provider"], sources["qul-ms-292"]["provider"])
        self.assertEqual(sources["qurancom-ms-39"]["path"], "sources/quran.com/source.json")
        self.assertEqual(sources["qul-ms-292"]["path"], "sources/qul/resources/292-basamia/source.json")

    def test_qul_inventory_records_export_state(self):
        report = json.loads(
            (REPO_ROOT / "sources/qul/inventory.json").read_text(encoding="utf-8")
        )
        resources = {item["source_key"]: item for item in report["resources"]}

        self.assertEqual(resources["qul-ms-292"]["authentication_status"], "browser_download_succeeded")
        self.assertEqual(resources["qul-ms-292"]["text_audit_status"], "key_set_validated_candidate_review_pending")
        self.assertEqual(resources["qul-130-metadata-anomaly"]["download_status"], "excluded")

    def test_imported_qurancom_findings_are_197_confirmed_records(self):
        ledger = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
        findings = ledger["findings"]
        imported = [
            finding
            for finding in findings
            if finding["source_key"] == "qurancom-ms-39"
            and finding["status"] == "confirmed"
        ]

        self.assertEqual(len(imported), 197)
        required = {
            "source_key",
            "resource_id",
            "status",
            "verse_key",
            "observed",
            "proposed",
            "evidence",
            "reviewer",
            "upstream_ticket",
        }
        self.assertTrue(required.issubset(imported[0]))
        self.assertTrue(all(finding["source_key"] == "qurancom-ms-39" for finding in findings))
        qul_ledger = json.loads((REPO_ROOT / "sources/qul/findings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(qul_ledger["findings"]), 180)
        self.assertTrue(all(finding["status"] == "candidate" for finding in qul_ledger["findings"]))

    def test_qul_patch_is_derived_and_not_auto_approved(self):
        patch = load_correction_manifest(QUL_PATCH_PATH)

        self.assertEqual(patch["patch_status"], "candidate")
        self.assertEqual(patch["base_export"]["record_count"], EXPECTED_VERSE_COUNT)
        self.assertEqual(len(patch["corrections"]), 180)
        self.assertEqual(filter_corrections(patch, source_key="qul-ms-292"), [])
        self.assertFalse((REPO_ROOT / "sources/qul/resources/292-basamia/simple.json").exists())
        self.assertFalse(any((REPO_ROOT / "sources/qul/resources/292-basamia").glob("*.sqlite")))

    def test_expected_quran_key_set_has_6236_keys(self):
        keys = expected_verse_keys()
        self.assertEqual(len(keys), EXPECTED_VERSE_COUNT)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[0], "1:1")
        self.assertEqual(keys[-1], "114:6")

    def test_validator_reports_complete_key_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "complete.json"
            path.write_text(
                json.dumps({key: "teks" for key in expected_verse_keys()}, ensure_ascii=False),
                encoding="utf-8",
            )

            report = validate_export(path, source_key="qul-ms-292")

        self.assertTrue(report.is_valid)
        self.assertEqual(report.record_count, EXPECTED_VERSE_COUNT)
        self.assertEqual(report.duplicates, [])
        self.assertEqual(report.missing, [])
        self.assertEqual(report.unexpected, [])

    def test_validator_detects_missing_duplicate_and_unexpected_keys(self):
        rows = [{"verse_key": key, "text": "teks"} for key in expected_verse_keys()]
        rows = [row for row in rows if row["verse_key"] != "2:4"]
        rows.append({"verse_key": "1:1", "text": "duplicate"})
        rows.append({"verse_key": "115:1", "text": "unexpected"})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            report = validate_export(path, source_key="qul-ms-292")

        self.assertFalse(report.is_valid)
        self.assertIn("2:4", report.missing)
        self.assertEqual(report.duplicates, ["1:1"])
        self.assertEqual(report.unexpected, ["115:1"])

    def test_loader_accepts_qul_key_value_json_and_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            json_path = directory / "qul.json"
            json_path.write_text(json.dumps({"1:1": "satu", "1:2": "dua"}), encoding="utf-8")
            json_rows = load_export_rows(json_path)

            sqlite_path = directory / "qul.sqlite"
            with sqlite3.connect(sqlite_path) as database:
                database.execute("CREATE TABLE translation (ayah_key TEXT, text TEXT)")
                database.executemany(
                    "INSERT INTO translation VALUES (?, ?)",
                    [("1:1", "satu"), ("1:2", "dua")],
                )
                database.commit()
            sqlite_rows = load_export_rows(sqlite_path)

        self.assertEqual(json_rows.records, sqlite_rows.records)
        self.assertEqual(json_rows.format, "json-key-value")
        self.assertEqual(sqlite_rows.format, "sqlite")

    def test_normalization_is_analysis_only(self):
        original = "  Allah\u00a0 Maha  "
        normalized = normalize_for_analysis(original)

        self.assertEqual(normalized, "allah maha")
        self.assertEqual(original, "  Allah\u00a0 Maha  ")

    def test_cross_source_difference_is_a_candidate_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            left = directory / "left.json"
            right = directory / "right.json"
            left.write_text(json.dumps({"1:1": "Segala puji"}), encoding="utf-8")
            right.write_text(json.dumps({"1:1": "Segala pujian"}), encoding="utf-8")

            differences = compare_exports(
                left,
                right,
                left_source_key="qurancom-ms-39",
                right_source_key="qul-ms-292",
            )

        self.assertEqual(len(differences), 1)
        self.assertEqual(differences[0]["status"], "candidate")
        self.assertEqual(differences[0]["source_key"], "qurancom-ms-39")
        self.assertEqual(differences[0]["comparison_source_key"], "qul-ms-292")
        self.assertFalse(differences[0]["is_error"])

    def test_correction_filter_requires_matching_source_and_confirmed_status(self):
        manifest = load_correction_manifest(CORRECTIONS_PATH)
        approved = filter_corrections(manifest, source_key="qurancom-ms-39")

        self.assertEqual(len(approved), 197)
        self.assertTrue(all(item["status"] == "confirmed" for item in approved))
        with self.assertRaises(SourceMismatchError):
            filter_corrections(manifest, source_key="qul-ms-292")

    def test_apply_corrections_ignores_candidate_and_is_idempotent(self):
        manifest = {
            "version": 1,
            "source": "fixture",
            "source_key": "qurancom-ms-39",
            "scope": "fixture",
            "corrections": [
                {
                    "verse_key": "1:1",
                    "find": "terentu",
                    "replace": "tertentu",
                    "status": "confirmed",
                },
                {
                    "verse_key": "1:2",
                    "find": "salah",
                    "replace": "betul",
                    "status": "candidate",
                },
            ],
        }
        texts = {"1:1": "teks terentu", "1:2": "salah"}

        updated, first_stats = apply_corrections(texts, manifest, source_key="qurancom-ms-39")
        updated_again, second_stats = apply_corrections(
            updated, manifest, source_key="qurancom-ms-39"
        )

        self.assertEqual(updated["1:1"], "teks tertentu")
        self.assertEqual(updated["1:2"], "salah")
        self.assertEqual(updated_again, updated)
        self.assertEqual(first_stats["applied"], 1)
        self.assertEqual(second_stats["already_correct"], 1)


if __name__ == "__main__":
    unittest.main()
