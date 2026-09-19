# Jev Advisory Review Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `jev-review` command that sends source-scoped candidate findings to TypeSafe Jev and writes a separate advisory report without changing audit statuses or source text.

**Architecture:** Keep the TypeSafe HTTP transport and report orchestration in a focused `quran_ms_audit/jev.py` module. Extend the existing argparse entry point with a command that loads a findings ledger, enforces one source key and candidate-only selection, and serializes the advisory report. Use only the Python standard library and inject the HTTP opener in tests.

**Tech Stack:** Python 3, `urllib.request`, JSON, `unittest`, existing `quran_ms_audit` CLI.

## Global Constraints

- The pilot is advisory-only and must never promote a finding or apply a correction.
- The default input status is `candidate`.
- The requested `source_key` must match every selected finding before any API request.
- The API key comes from `TYPESAFE_API_KEY` in the environment or an ignored `.env` file and is never printed or stored in reports.
- Full translation exports are not sent; one finding’s source-scoped fields are sent per request.
- No TypeSafe SDK dependency is added.

### Task 1: Define the Jev client and report contract with failing tests

**Files:**
- Modify: `tests/test_audit_toolkit.py`
- Create: `quran_ms_audit/jev.py` (only after the tests fail)

**Interfaces:**
- `JevClient(api_key: str, endpoint: str = DEFAULT_ENDPOINT, model: str = DEFAULT_MODEL, timeout: float = 30.0, opener: Callable = urlopen)`
- `JevClient.review(finding: Mapping[str, Any]) -> Dict[str, Any]`
- `review_findings(findings: Sequence[Mapping[str, Any]], source_key: str, client: JevClient, limit: Optional[int] = None) -> Dict[str, Any]`
- `load_api_key(environment: Mapping[str, str], env_file: Optional[Path] = None) -> str`

- [ ] **Step 1: Add failing tests for payload and typed response handling.**

  Add a fake response/opener in `tests/test_audit_toolkit.py` and tests that assert:

  ```python
  def test_jev_client_sends_scoped_state_and_returns_answers():
      finding = {
          "source_key": "qul-ms-292", "resource_id": "292", "verse_key": "24:53",
          "status": "candidate", "observed": "sebebar-benar",
          "proposed": "sebenar-benar", "evidence": "review evidence",
      }
      client = JevClient("secret", opener=fake_opener)
      result = client.review(finding)
      self.assertEqual(result["answers"]["finding_kind"]["choice"], "spelling_or_typo")
      self.assertEqual(sent_payload["state"], json.dumps({
          "source_key": "qul-ms-292", "resource_id": "292", "verse_key": "24:53",
          "observed": "sebebar-benar", "proposed": "sebenar-benar",
          "evidence": "review evidence",
      }, ensure_ascii=False))
  ```

- [ ] **Step 2: Add failing tests for source/status gates and advisory report shape.**

  Assert that `review_findings` selects only candidates, respects `limit`, preserves `source_key`, `resource_id`, `verse_key`, and `status`, and emits `advisory_only: True`. Assert that a mismatching finding raises `SourceMismatchError` before the fake opener is called.

- [ ] **Step 3: Add failing tests for credentials and per-finding API errors.**

  Assert that environment credentials win, a `.env` value is accepted when the environment is empty, missing credentials raise `JevClientError`, and a failed request becomes a result-level `error` while later findings are still reviewed.

- [ ] **Step 4: Run the focused tests and verify they fail for missing `quran_ms_audit.jev`.**

  Run:

  ```bash
  python3 -m unittest tests.test_audit_toolkit -v
  ```

  Expected: failures importing the new Jev interfaces, not unrelated test errors.

### Task 2: Implement the minimal standard-library Jev module

**Files:**
- Create: `quran_ms_audit/jev.py`
- Modify: `quran_ms_audit/__init__.py`
- Test: `tests/test_audit_toolkit.py`

**Interfaces:**
- `DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"`
- `DEFAULT_MODEL = "jev-latest"`
- `REVIEW_QUESTIONS` contains one Choice question named `finding_kind` and one Noul question named `specialist_review`.
- `JevClient.review` raises `JevClientError` for transport, HTTP, JSON, or missing-answer failures.

- [ ] **Step 1: Implement `load_api_key` with no logging.**

  Return `environment["TYPESAFE_API_KEY"]` when non-empty; otherwise parse only `KEY=VALUE` lines from the optional env file, strip one matching pair of quotes, and raise `JevClientError("TYPESAFE_API_KEY is not configured")` when empty.

- [ ] **Step 2: Implement `JevClient.review`.**

  Serialize only the six scoped finding fields into `state`, POST `{state, model, questions}` to the documented endpoint with a Bearer header, decode JSON, require an `answers` object, and return `model`, `answers`, and optional `usage`. Do not include the API key in any exception text.

- [ ] **Step 3: Implement `review_findings`.**

  Validate every input finding’s `source_key` before contacting Jev, select `status == "candidate"`, apply `limit`, call the client once per selected finding, and return a versioned report with `advisory_only: True`, counts, selected identity fields, answers, usage, and result-level errors.

- [ ] **Step 4: Run focused tests and then the full suite.**

  Run:

  ```bash
  python3 -m unittest tests.test_audit_toolkit -v
  python3 -m unittest discover -s tests -v
  ```

  Expected: all tests pass, including the new Jev tests.

- [ ] **Step 5: Commit the client/report unit.**

  ```bash
  git add quran_ms_audit/jev.py quran_ms_audit/__init__.py tests/test_audit_toolkit.py
  git commit -m "feat: add advisory Jev review client"
  ```

### Task 3: Add the read-only CLI command

**Files:**
- Modify: `quran_ms_audit/__main__.py`
- Modify: `tests/test_audit_toolkit.py`
- Test output: ignored `sources/qul/reports/jev-292-pilot.json`

**Interfaces:**
- Command: `python3 -m quran_ms_audit jev-review FINDINGS --source-key SOURCE --output REPORT [--env-file FILE] [--limit N]`
- The command loads an object ledger’s `findings` list, obtains the key without printing it, calls `review_findings`, and writes JSON through the existing `_write_json` helper.

- [ ] **Step 1: Add a failing CLI parser test.**

  Assert that the parser accepts `jev-review`, requires `--source-key`, defaults `--env-file` to `.env`, and accepts `--limit`.

- [ ] **Step 2: Implement the parser branch.**

  Load the ledger, reject a non-object or missing `findings` list with a concise `SystemExit`, load the key via `load_api_key(os.environ, args.env_file)`, run the report, and write it. Do not mutate or rewrite the input ledger.

- [ ] **Step 3: Run CLI tests and command help.**

  Run:

  ```bash
  python3 -m unittest tests.test_audit_toolkit -v
  python3 -m quran_ms_audit jev-review --help
  git diff --check
  ```

- [ ] **Step 4: Commit the CLI unit.**

  ```bash
  git add quran_ms_audit/__main__.py tests/test_audit_toolkit.py
  git commit -m "feat: expose Jev advisory review command"
  ```

### Task 4: Run one bounded live pilot and verify repository safety

**Files:**
- Create locally only: `sources/qul/reports/jev-292-pilot.json` (ignored, do not commit)
- Do not modify: `sources/qul/findings.json`, correction manifests, or exports

- [ ] **Step 1: Run one live request against one QUL candidate.**

  ```bash
  python3 -m quran_ms_audit jev-review \
    sources/qul/findings.json \
    --source-key qul-ms-292 \
    --env-file .env \
    --limit 1 \
    --output sources/qul/reports/jev-292-pilot.json
  ```

- [ ] **Step 2: Inspect only report metadata and advisory flags.**

  Confirm the report has `source_key == "qul-ms-292"`, `selected_count == 1`, `advisory_only == true`, a Jev model, and typed answers. Do not print the API key or copy the report into Git.

- [ ] **Step 3: Verify the input ledger and manifests are unchanged.**

  ```bash
  git status --short
  git diff --check
  python3 -m unittest discover -s tests -v
  ```

- [ ] **Step 4: Commit only source code and tests if verification is clean.**

  ```bash
  git add quran_ms_audit tests/test_audit_toolkit.py
  git commit -m "test: verify bounded Jev advisory pilot"
  ```
