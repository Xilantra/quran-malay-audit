# Quran Malay Translation Audit

[![CI](https://github.com/Xilantra/quran-malay-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/Xilantra/quran-malay-audit/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/Xilantra/quran-malay-audit?display_name=tag)](https://github.com/Xilantra/quran-malay-audit/releases)

This is an independent, deterministic audit toolkit for Quran Malay translation data. It keeps each provider and resource ID in its own source track, validates local JSON or SQLite exports against the canonical 6,236 verse keys, and records reviewable differences without treating one translation as proof that another is wrong.

## Source-first layout

```
sources/
  registry.json
  quran.com/
    source.json
    corrections.json
    findings.json
  qul/
    source.json
    inventory.json
    findings.json
    resources/
      292-basamia/source.json
      130-metadata-anomaly/source.json
    reports/
schema/                 shared JSON contracts
quran_ms_audit/         shared parser, validator, comparator, and correction gate
tests/                  focused regression tests
```

The [Quran.com source track](sources/quran.com/README.md) and the [QUL source track](sources/qul/README.md) are intentionally separate. The registry at [sources/registry.json](sources/registry.json) is only an index of source identity and paths.

The generated human-readable comparison is [comparison.md](comparison.md). It compares the Quran.com correction track with the tracked QUL resource without including the original translation export.

Current source status:

| Source track | Resource | State |
| --- | --- | --- |
| Quran.com | Resource 39, Abdullah Muhammad Basmeih | 197 confirmed textual corrections |
| QUL | Resource 292, Abdullah Basamia | JSON export validated; 180 candidate patch records |
| QUL | Resource 130 | Excluded metadata and language anomaly |

No full translation dump, original SQL file, generated database, credential, or provider-internal data is committed. The intended distributable is a source-scoped patch, not the original export.

## Safe local workflow

Choose one exact source key and validate a local export before comparing or applying anything:

```bash
python3 -m quran_ms_audit validate \
  exports/qul-292-simple.json \
  --source-key qul-ms-292 \
  --output sources/qul/reports/qul-292-validation.json
```

The validator accepts key-value JSON, nested-array JSON, record-list JSON, translation-list JSON, and SQLite tables with `verse_key` or `ayah_key` plus `text`. It reports duplicate, missing, unexpected, and empty keys. It does not rewrite source text.

Compare two explicitly labelled source exports:

```bash
python3 -m quran_ms_audit compare \
  exports/qurancom-39-key-value.json \
  exports/qul-292-simple.json \
  --left-source-key qurancom-ms-39 \
  --right-source-key qul-ms-292 \
  --output sources/qul/reports/qurancom-vs-qul-candidates.json
```

Comparison output is `candidate` evidence with `is_error: false`. Wording, spelling, punctuation, and formatting differences require independent review.

Apply only a source-matching `confirmed` correction manifest:

```bash
python3 -m quran_ms_audit apply \
  exports/qurancom-39-key-value.json \
  --manifest sources/quran.com/corrections.json \
  --source-key qurancom-ms-39 \
  --output sources/quran.com/reports/qurancom-39-corrected.json
```

The application is guarded and idempotent. It requires the expected `find` text or recognizes that the `replace` text is already present. It never turns a candidate comparison into an approved correction.

## Upstream references

- [Quran Foundation Content API documentation](https://api-docs.quran.com/docs/content_apis_versioned/4.0.0/content-apis/)
- [QUL Malay documentation](https://qul.tarteel.ai/docs/malay)
- [QUL contribute-data guide](https://qul.tarteel.ai/docs/contribute-data)
- [QUL issue tracker](https://github.com/TarteelAI/quranic-universal-library/issues)

Review provider terms and attribution requirements before redistributing any translation text. Keep user-provided exports in the ignored `exports/` directory and record their retrieval date, version, and SHA-256 in a local report.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m quran_ms_audit --help
git diff --check
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for source-scoped review rules and local checks. Use the [translation finding template](https://github.com/Xilantra/quran-malay-audit/issues/new?template=translation-finding.yml) for a new candidate, and read [SECURITY.md](SECURITY.md) before reporting a sensitive issue.
