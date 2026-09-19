# Jev advisory review pilot

## Goal

Add a read-only pilot that sends source-scoped candidate findings to TypeSafe Jev for structured triage. The pilot will help prioritize human review, but it will never promote a finding, change source text, or apply a correction.

## Scope

- Add a small Python client using the documented `POST /v1/systemone` API.
- Read `TYPESAFE_API_KEY` from the process environment or an ignored local `.env` file.
- Add a `jev-review` CLI command that accepts a findings ledger, requires its source key, and writes a separate JSON advisory report.
- Evaluate only records whose status is `candidate` by default.
- Send source identity, verse key, observed text, proposed text, and evidence for one finding at a time.
- Ask atomic questions for finding category and specialist-review need.
- Preserve Jev probabilities and confidence values in the report, together with `advisory_only: true`.
- Record request failures per finding and continue processing later findings.

## Non-goals

- No automatic status changes or correction-manifest changes.
- No translation export upload, full-database batching, or source-text rewrite.
- No confidence threshold that can approve a finding.
- No new dependency on the TypeSafe SDK; use the Python standard library for the pilot.

## Data flow

1. Load the findings JSON and verify that every selected finding has the requested source key.
2. Select candidate records, optionally bounded by a CLI limit.
3. Build one JSON API request per finding with fixed, reviewable question definitions.
4. Store the typed answers, probabilities, confidence, model, and usage in a separate report.
5. Leave the input ledger, manifests, and exports unchanged.

## Safety and errors

- Missing credentials fail before any request.
- A non-success HTTP response or malformed response becomes a report error for that verse rather than a correction.
- The API key is never printed or written to a report.
- The command rejects a source-key mismatch before contacting the API.
- The output path is explicit and should normally live under the ignored reports directory.

## Verification

- Unit tests cover request construction, source/status gating, response parsing, credential handling, and per-finding error capture using a fake transport.
- Run the complete unittest suite and `git diff --check`.
- Run one live request against a single candidate only after the local tests pass; do not commit the resulting report if it contains provider text.
