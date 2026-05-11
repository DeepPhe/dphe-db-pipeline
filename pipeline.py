#!/usr/bin/env python3
"""
Full DeepPhe pipeline: source data → deepphe.sqlite3 → extracted concepts/summaries.

Stage 1 — OMAP importer (omap-data-importer)
  Reads source data (CSV / MySQL / JSON) and builds deepphe.sqlite3, which contains
  CALCULATED_PATIENT_DATA, CALCULATED_DX_DATA, and CALCULATED_PT_ICD_CODES.

Stage 2 — Concept extractor (deeppheconceptextractor)
  Reads deepphe_sqlite_compressed (DeepPhe NLP blobs) and the deepphe.sqlite3 built
  in Stage 1, then runs extraction → parse → import → patient summaries.

Usage:
    # Full run (both stages)
    python pipeline.py --config src/importer/config.json

    # Stage 1 only (build deepphe.sqlite3 from source data)
    python pipeline.py --config src/importer/config.json --only-stage1

    # Stage 2 only (skip importer, deepphe.sqlite3 already exists)
    python pipeline.py --skip-stage1

    # Pass explicit database paths
    python pipeline.py \\
        --config src/importer/config.json \\
        --database /path/to/deepphe_sqlite_compressed \\
        --omop-database /path/to/deepphe.sqlite3
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_IMPORTER_CONFIG = _BASE_DIR / "src" / "importer" / "config.json"
_DEFAULT_DB = _BASE_DIR / "deepphe" / "deepphe_sqlite_compressed"
_DEFAULT_OMOP_DB = _BASE_DIR / "deepphe" / "deepphe.sqlite3"


def _run(script: Path, extra_args: list[str] | None = None) -> None:
    cmd = [sys.executable, str(script)] + (extra_args or [])
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=_BASE_DIR, check=True)


def _run_stage1(config: Path, source_type: str | None) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 1 — OMAP importer: building deepphe.sqlite3")
    logger.info("=" * 60)

    args = ["--config", str(config)]
    if source_type:
        args += ["--source-type", source_type]

    _run(_BASE_DIR / "src" / "importer" / "run.py", args)
    logger.info("Stage 1 complete.")


def _run_stage2(database: Path | None, omop_database: Path | None, skip_clean: bool) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 2 — Concept extractor")
    logger.info("=" * 60)

    args: list[str] = []
    if database:
        args += ["--database", str(database)]
    if omop_database:
        args += ["--omop-database", str(omop_database)]
    if skip_clean:
        args.append("--skip-clean")

    _run(_BASE_DIR / "src" / "scripts" / "regenerate_data_pipeline.py", args)
    logger.info("Stage 2 complete.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Full DeepPhe pipeline: source data → deepphe.sqlite3 → extracted concepts."
    )

    # Stage selection
    stage = parser.add_mutually_exclusive_group()
    stage.add_argument(
        "--skip-stage1",
        action="store_true",
        help="Skip Stage 1 (OMAP importer). Use when deepphe.sqlite3 already exists.",
    )
    stage.add_argument(
        "--only-stage1",
        action="store_true",
        help="Run Stage 1 only (build deepphe.sqlite3, then stop).",
    )

    # Stage 1 options
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_IMPORTER_CONFIG,
        help=f"Path to the OMAP pipeline config JSON (default: {_DEFAULT_IMPORTER_CONFIG}).",
    )
    parser.add_argument(
        "--source-type",
        choices=("csv", "mysql", "json"),
        default=None,
        help="Override SOURCE_TYPE from .env for Stage 1 (csv | mysql | json).",
    )

    # Stage 2 options
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=(
            "Path to deepphe_sqlite_compressed for Stage 2 "
            f"(default: {_DEFAULT_DB})."
        ),
    )
    parser.add_argument(
        "--omop-database",
        type=Path,
        default=None,
        help=(
            "Path to deepphe.sqlite3 for Stage 2 demographics "
            f"(default: {_DEFAULT_OMOP_DB})."
        ),
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Pass --skip-clean to Stage 2 (do not delete existing extracted CSVs).",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("DEEPPHE FULL PIPELINE")
    logger.info("Base directory: %s", _BASE_DIR)
    logger.info("=" * 60)

    if not args.skip_stage1:
        config = args.config.resolve()
        if not config.exists():
            logger.error("Config not found: %s", config)
            return 1
        _run_stage1(config, args.source_type)

    if not args.only_stage1:
        database = args.database.resolve() if args.database else None
        omop_database = args.omop_database.resolve() if args.omop_database else None
        _run_stage2(database, omop_database, args.skip_clean)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
