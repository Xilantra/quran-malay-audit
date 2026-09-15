#!/usr/bin/env python3
"""Convenience wrapper for ``python3 -m quran_ms_audit``."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quran_ms_audit.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
