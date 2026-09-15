# QUL source track

This folder contains the Quranic Universal Library (QUL/Tarteel) catalogue audit and keeps each resource in its own subfolder.

| Resource folder | Source key | Current state |
| --- | --- | --- |
| `resources/292-basamia/` | `qul-ms-292` | 6,236-key JSON export validated; 180 candidate patch records |
| `resources/130-metadata-anomaly/` | `qul-130-metadata-anomaly` | Excluded because the page is tagged Malayalam and previews Malayalam script |

Shared QUL files:

- `source.json`: QUL catalogue-level descriptor.
- `inventory.json`: official catalogue verification record.
- `findings.json`: QUL-only finding ledger, including the 180 candidate records for resource 292.
- `resources/292-basamia/patch.json`: derived candidate patch. It contains no original export or SQL file.
- `inventory.md`: human-readable catalogue notes and the local export workflow.

The [QUL Malay documentation](https://qul.tarteel.ai/docs/malay) is the catalogue reference for this track. Resource 292 provided a complete `simple.json` export, which validated against all 6,236 verse keys. The original export remains outside this repository. The derived patch has 180 exact phrase matches and stays `candidate` until QUL-specific review confirms them.

```bash
python3 -m quran_ms_audit validate \
  exports/qul-292-simple.json \
  --source-key qul-ms-292 \
  --output sources/qul/reports/qul-292-validation.json
```

Use the [QUL contribute-data guide](https://qul.tarteel.ai/docs/contribute-data) for upstream review and verify resource-specific licensing before redistribution.
