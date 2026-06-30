#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Compatibility wrapper for the packaged DeepPhe pipeline CLI."""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

def main() -> int:
    """Load and run the packaged CLI after frozen-process initialization."""
    from dphe_db_pipeline.pipeline import main as package_main

    return package_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
