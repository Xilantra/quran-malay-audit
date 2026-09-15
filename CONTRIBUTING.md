# Contributing

Thank you for helping improve the Quran Malay translation audit.

## Before opening a change

1. Choose one exact `source_key` and `resource_id` from `sources/registry.json`.
2. Keep provider tracks separate. A wording difference between sources is not automatically an error.
3. Validate any local export against the 6,236 canonical verse keys.
4. Record the official URL, retrieval date, version or digest, exact phrase, and evidence.
5. Use `candidate` until the source-specific review is complete.

Do not commit original translation exports, SQL databases, credentials, or unrelated application files. The distributable output is source metadata, findings, and reviewed patch records.

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q quran_ms_audit scripts tests
git diff --check
```

## Pull requests

Keep each pull request narrow and source-scoped. Include the provider resource URL and explain whether records are candidates or confirmed corrections. Do not mark a provider-side correction as accepted until the provider confirms it.

