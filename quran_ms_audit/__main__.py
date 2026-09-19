"""Command line entry point for local Quran Malay export audits."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .core import compare_exports, load_export_rows, validate_export
from .corrections import apply_corrections, load_correction_manifest
from .jev import JevClient, JevClientError, load_api_key, review_findings


def _write_json(value: Any, output: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output == "-":
        sys.stdout.write(rendered)
    else:
        Path(output).write_text(rendered, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m quran_ms_audit",
        description="Validate and compare source-separated Quran Malay translation exports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a local JSON or SQLite export")
    validate.add_argument("input", type=Path)
    validate.add_argument("--source-key", required=True)
    validate.add_argument("--output", default="-", help="JSON report path, or - for stdout")

    compare = subparsers.add_parser("compare", help="emit candidate differences between exports")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument("--left-source-key", required=True)
    compare.add_argument("--right-source-key", required=True)
    compare.add_argument("--output", default="-", help="JSON output path, or - for stdout")

    apply = subparsers.add_parser("apply", help="apply confirmed corrections to an export")
    apply.add_argument("input", type=Path)
    apply.add_argument("--manifest", type=Path, required=True)
    apply.add_argument("--source-key", required=True)
    apply.add_argument("--output", default="-", help="JSON output path, or - for stdout")

    jev_review = subparsers.add_parser(
        "jev-review",
        help="send candidate findings to Jev for advisory review",
    )
    jev_review.add_argument("input", type=Path)
    jev_review.add_argument("--source-key", required=True)
    jev_review.add_argument("--env-file", type=Path, default=Path(".env"))
    jev_review.add_argument("--limit", type=int)
    jev_review.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def main(argv: Any = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        _write_json(validate_export(args.input, source_key=args.source_key).to_dict(), args.output)
        return 0
    if args.command == "compare":
        _write_json(
            compare_exports(
                args.left,
                args.right,
                left_source_key=args.left_source_key,
                right_source_key=args.right_source_key,
            ),
            args.output,
        )
        return 0

    if args.command == "jev-review":
        try:
            ledger = json.loads(args.input.read_text(encoding="utf-8"))
        except OSError as error:
            raise SystemExit(f"could not read findings ledger: {error}") from error
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid findings ledger JSON: {error}") from error
        if not isinstance(ledger, dict) or not isinstance(ledger.get("findings"), list):
            raise SystemExit("findings ledger must be an object containing a findings list")
        try:
            api_key = load_api_key(os.environ, args.env_file)
            report = review_findings(
                ledger["findings"],
                args.source_key,
                JevClient(api_key),
                limit=args.limit,
            )
        except (JevClientError, ValueError) as error:
            raise SystemExit(str(error)) from error
        _write_json(report, args.output)
        return 0

    rows = load_export_rows(args.input)
    manifest = load_correction_manifest(args.manifest)
    texts: Dict[str, str] = {}
    for verse_key, text in rows.records:
        if verse_key in texts:
            raise SystemExit(f"duplicate verse key in input: {verse_key}")
        texts[verse_key] = text
    updated, stats = apply_corrections(texts, manifest, source_key=args.source_key)
    _write_json({"stats": stats, "texts": updated}, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
