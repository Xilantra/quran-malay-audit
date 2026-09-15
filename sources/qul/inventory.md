# QUL catalogue inventory audit

Audit date: 2026-09-15

Scope: official QUL catalogue and resource-page metadata, plus validation of the tracked JSON export. The original translation export was not committed.

## Verified catalogue entries

The [QUL Malay documentation](https://qul.tarteel.ai/docs/malay) is the catalogue reference for the tracked resource:

| Source key | Resource | Verification | Text audit |
| --- | --- | --- | --- |
| `qul-ms-292` | Abdullah Basamia | [Resource 292](https://qul.tarteel.ai/resources/translation/292) is tagged Translation and Malay. A `simple.json` export was downloaded and validated against all 6,236 verse keys. | 180 exact phrase matches are recorded as candidate patch records pending QUL-specific review. |

The official [Malayalam documentation](https://qul.tarteel.ai/docs/malayalam) links resource 130 under the title `Malay Translation(Abdul Hameed and Kunhi)`. Its [detail page](https://qul.tarteel.ai/resources/translation/130) is tagged Malayalam, and the preview renders Malayalam script. It is recorded as `qul-130-metadata-anomaly` and excluded from the Malay track.

## Blocked and pending work

- Resource 292: the JSON export is valid and remains outside the repository. The derived patch records 180 exact phrase matches. No original export or SQL file is distributed.
- Resource 130: language metadata must be resolved by QUL before any Malay audit.

## Local export command

Put a user-provided export in the ignored `exports/` directory and validate it without committing the file:

```bash
python3 -m quran_ms_audit validate \
  exports/qul-292-simple.json \
  --source-key qul-ms-292 \
  --output sources/qul/reports/qul-292-validation.json
```

Record the export version, retrieval date, and SHA-256 in a follow-up report. The validator checks all 6,236 canonical verse keys, duplicate keys, missing keys, unexpected keys, and empty text. It does not decide whether a translation phrase is correct. For resource 292, distribute only the derived patch at `resources/292-basamia/patch.json` after its candidate records are reviewed.

## Upstream paths

QUL's [contribute-data guide](https://qul.tarteel.ai/docs/contribute-data) describes CMS review and community contributions. The [QUL issue tracker](https://github.com/TarteelAI/quranic-universal-library/issues) is available for correction work. Include the resource URL, exact verse key, observed and proposed text, format, export digest, and a minimal reproducible excerpt. Review the exact resource licensing before redistribution.
