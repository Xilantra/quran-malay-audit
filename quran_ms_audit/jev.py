"""Advisory TypeSafe Jev review for source-scoped audit findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .corrections import SourceMismatchError


DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
SCOPED_FIELDS = (
    "source_key",
    "resource_id",
    "verse_key",
    "observed",
    "proposed",
    "evidence",
)

REVIEW_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "finding_kind": {
        "type": "choice",
        "instructions": "What kind of review issue does this finding most likely represent?",
        "criteria": {
            "spelling_or_typo": "A likely spelling or typographical error with no intended meaning change.",
            "punctuation_or_format": "A punctuation, spacing, or formatting issue.",
            "wording_or_semantics": "A wording or meaning issue that may require linguistic or scholarly review.",
            "insufficient_evidence": "The supplied record does not contain enough evidence to classify it.",
        },
    },
    "specialist_review": {
        "type": "noul",
        "instructions": "Does this finding require specialist human review before any correction could be confirmed?",
    },
}


class JevClientError(RuntimeError):
    """Raised when Jev cannot produce a typed answer."""


def load_api_key(
    environment: Mapping[str, str],
    env_file: Optional[Path] = None,
) -> str:
    """Load the TypeSafe key without printing or persisting it."""

    key = environment.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key

    if env_file is not None and Path(env_file).is_file():
        for raw_line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() != "TYPESAFE_API_KEY":
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value.strip():
                return value.strip()

    raise JevClientError("TYPESAFE_API_KEY is not configured")


def _state_for_finding(finding: Mapping[str, Any]) -> str:
    missing = [field for field in SCOPED_FIELDS if field not in finding]
    if missing:
        raise JevClientError(f"finding is missing required fields: {', '.join(missing)}")
    return json.dumps(
        {field: finding[field] for field in SCOPED_FIELDS},
        ensure_ascii=False,
    )


class JevClient:
    """Small standard-library client for the TypeSafe System One endpoint."""

    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not api_key.strip():
            raise JevClientError("TYPESAFE_API_KEY is not configured")
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout
        self.opener = opener

    def review(self, finding: Mapping[str, Any]) -> Dict[str, Any]:
        payload = {
            "state": _state_for_finding(finding),
            "model": self.model,
            "questions": REVIEW_QUESTIONS,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise JevClientError(f"Jev request failed with HTTP {error.code}") from error
        except URLError as error:
            raise JevClientError(f"Jev request failed: {error.reason}") from error
        except (OSError, TimeoutError) as error:
            raise JevClientError(f"Jev request failed: {error}") from error
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise JevClientError("Jev returned invalid JSON") from error

        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            raise JevClientError("Jev response is missing answers")
        if not all(question in body["answers"] for question in REVIEW_QUESTIONS):
            raise JevClientError("Jev response is missing a requested answer")

        return {
            "model": body.get("model", self.model),
            "answers": body["answers"],
            "usage": body.get("usage"),
        }


def review_findings(
    findings: Sequence[Mapping[str, Any]],
    source_key: str,
    client: JevClient,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Review candidate findings and return a separate advisory report."""

    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    for finding in findings:
        if finding.get("source_key") != source_key:
            raise SourceMismatchError(
                f"Finding source {finding.get('source_key')!r} does not match requested {source_key!r}"
            )

    candidates = [finding for finding in findings if finding.get("status") == "candidate"]
    selected = candidates if limit is None else candidates[:limit]
    results = []

    for finding in selected:
        identity = {
            "source_key": finding["source_key"],
            "resource_id": finding.get("resource_id"),
            "verse_key": finding.get("verse_key"),
            "status": finding.get("status"),
        }
        try:
            review = client.review(finding)
        except JevClientError as error:
            results.append({**identity, "advisory_only": True, "error": str(error)})
        else:
            results.append({**identity, "advisory_only": True, **review})

    return {
        "version": 1,
        "provider": "typesafe",
        "model": client.model,
        "source_key": source_key,
        "advisory_only": True,
        "input_count": len(findings),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "results": results,
    }
