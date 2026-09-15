# Agent guide for Quran Malay translation audits

This repository is an audit record, not a translation rewriting tool. Preserve source identity and require human review at every correction boundary.

## Source layout

- `sources/registry.json` is the source index.
- `sources/quran.com/` contains only the Quran.com resource track.
- `sources/qul/` contains the QUL catalogue, resource records, and QUL findings.
- `schema/`, `quran_ms_audit/`, and `tests/` are shared infrastructure.

Before touching a finding:

1. Read the matching source record and select one exact `source_key`.
2. Confirm its `resource_id`, translator, retrieval date, version, license status, and download status.
3. Read the finding from the matching source folder. A finding is not portable between providers, translators, or resource IDs.
4. For a local export, run the validator and keep its report. A valid key set does not prove that the translation text is correct.
5. Treat `qul-130-metadata-anomaly` as excluded. Do not relabel it as Malay because its title contains the word Malay.

## Finding status rules

Allowed statuses are `candidate`, `confirmed`, `rejected`, `submitted`, and `fixed`.

- `candidate`: a spelling, wording, punctuation, or format difference that still needs review.
- `confirmed`: a reviewer has approved the exact source-scoped change and its precondition is known.
- `rejected`: reviewed and intentionally not accepted.
- `submitted`: sent upstream, but not yet confirmed as published or accepted.
- `fixed`: verified in the named upstream source version.

Never auto-apply `candidate`, `rejected`, `submitted`, or `fixed` records. The default application gate accepts only `confirmed`, and it requires the requested source key to equal the manifest source key. A difference between two QUL resources is evidence for review, not an error and not a correction.

## Applying an approved correction

Use the source-specific manifest, for example `sources/quran.com/corrections.json`:

```bash
python3 -m quran_ms_audit apply \
  exports/source-key-export.json \
  --manifest sources/quran.com/corrections.json \
  --source-key qurancom-ms-39 \
  --output sources/quran.com/reports/source-key-corrected.json
```

The application is guarded by verse key, exact `find` text, whole-word boundaries, and optional `occurrences`. If the precondition is absent or ambiguous, stop and review the source export. Do not weaken the precondition to make a build pass.

## Provenance to preserve

When adding or changing a finding, record:

- `source_key` and `resource_id`.
- The provider's official URL.
- Retrieval date and source version or export digest.
- Exact `verse_key`, `observed`, and `proposed` values.
- Evidence and reviewer identity. Use `null` when no reviewer or ticket exists. Do not invent a person, ticket, or upstream approval.
- `upstream_ticket` only when a real issue, CMS record, or provider reference exists.

Keep full exports and databases outside Git. Do not add credentials or generated SQLite databases.

## QUL local-export path

QUL pages advertise JSON and SQLite formats, but an export may require sign-in or a user-provided download. Put the file under the ignored `exports/` directory and run:

```bash
python3 -m quran_ms_audit validate \
  exports/qul-292-simple.json \
  --source-key qul-ms-292 \
  --output sources/qul/reports/qul-292-validation.json
```

Use `qul-ms-292` for the tracked Malay resource. Never use `qul-130-metadata-anomaly` as a Malay source until QUL resolves the metadata and language mismatch.

For resource 292, distribute only the derived patch at `sources/qul/resources/292-basamia/patch.json`. Keep the downloaded export outside Git and never add the original export or SQL file to this repository. Candidate patch records require QUL-specific review before they can be marked `confirmed`.

## Integration boundary

Consumers should gate a correction by source identity, status, and exact observed text:

```swift
struct ApprovedCorrection: Decodable {
    let sourceKey: String
    let resourceID: String
    let status: String
    let verseKey: String
    let observed: String
    let proposed: String
}

guard correction.sourceKey == activeSourceKey,
      correction.resourceID == activeResourceID,
      correction.status == "confirmed",
      text == correction.observed else {
    return text
}
return text.replacingOccurrences(of: correction.observed,
                                 with: correction.proposed)
```

For production integrations, preserve the original source text for audit display and add an exact occurrence check equivalent to the Python gate.

## Upstream reporting

For QUL, follow the [contribute-data guide](https://qul.tarteel.ai/docs/contribute-data), request access through the QUL Tools page when appropriate, or open a [QUL GitHub issue](https://github.com/TarteelAI/quranic-universal-library/issues). For Quran.com resource 39, use the [Content API documentation](https://api-docs.quran.com/docs/content_apis_versioned/4.0.0/content-apis/) as the resource reference and the provider's current content-support path. Do not claim that a correction was accepted until the provider confirms it.
