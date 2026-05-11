#!/usr/bin/env python3
"""
Full DeepPhe pipeline: raw NLP output → deepphe_sqlite_compressed → deepphe.sqlite3 → extracted concepts/summaries.

Stage 0 — Loader (DeepPheOutputLoader)
  Reads raw DeepPhe NLP output files (directory or zip archives) and loads them
  into deepphe_sqlite_compressed (key = filename, value = compressed content).

Stage 1 — OMAP importer (omap-data-importer)
  Reads source demographic/diagnosis data (CSV / MySQL / JSON) and builds
  deepphe.sqlite3, which contains CALCULATED_PATIENT_DATA, CALCULATED_DX_DATA,
  and CALCULATED_PT_ICD_CODES.

Stage 2 — Concept extractor (deeppheconceptextractor)
  Reads deepphe_sqlite_compressed (Stage 0 output) and deepphe.sqlite3 (Stage 1
  output), then runs extraction → parse → import → patient summaries.

Usage:
    # Full run (all three stages)
    python pipeline.py --input-dir /path/to/deepphe/output \\
                       --config src/importer/config.json

    # Stage 0 only (load raw files into SQLite)
    python pipeline.py --input-dir /path/to/deepphe/output --only-stage0

    # Stage 0 + Stage 1 only
    python pipeline.py --input-dir /path/to/deepphe/output \\
                       --config src/importer/config.json \\
                       --only-stage1

    # Skip Stage 0 (deepphe_sqlite_compressed already built)
    python pipeline.py --skip-stage0 --config src/importer/config.json

    # Stage 2 only (both databases already exist)
    python pipeline.py --skip-stage0 --skip-stage1

    # Load from zip archives instead of a directory
    python pipeline.py --input-zip /path/to/archive.zip
    python pipeline.py --input-zipdir /path/to/zip/directory
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
_DEFAULT_COMPRESSED_DB = _BASE_DIR / "deepphe" / "deepphe_sqlite_compressed"
_DEFAULT_OMOP_DB = _BASE_DIR / "deepphe" / "deepphe.sqlite3"
_DEFAULT_IMPORTER_CONFIG = _BASE_DIR / "src" / "importer" / "config.json"


def _run(script: Path, extra_args: list[str] | None = None) -> None:
    cmd = [sys.executable, str(script)] + (extra_args or [])
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=_BASE_DIR, check=True)


def _run_stage0(
    input_dir: Path | None,
    input_zip: Path | None,
    input_zipdir: Path | None,
    compressed_db: Path,
) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 0 — Loader: building deepphe_sqlite_compressed")
    logger.info("=" * 60)

    args: list[str] = []

    if input_zip:
        args += [str(compressed_db), "--zip", str(input_zip)]
    elif input_zipdir:
        args += [str(compressed_db), "--zipdir", str(input_zipdir)]
    else:
        # Directory mode: positional args are input_dir then db_path
        args += [str(input_dir), str(compressed_db)]

    _run(_BASE_DIR / "src" / "loader" / "load_to_sqlite.py", args)
    logger.info("Stage 0 complete.")


def _run_stage1(config: Path, source_type: str | None) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 1 — OMAP importer: building deepphe.sqlite3")
    logger.info("=" * 60)

    args = ["--config", str(config)]
    if source_type:
        args += ["--source-type", source_type]

    _run(_BASE_DIR / "src" / "importer" / "run.py", args)
    logger.info("Stage 1 complete.")


def _run_stage2(
    compressed_db: Path | None,
    omop_db: Path | None,
    skip_clean: bool,
) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 2 — Concept extractor")
    logger.info("=" * 60)

    args: list[str] = []
    if compressed_db:
        args += ["--database", str(compressed_db)]
    if omop_db:
        args += ["--omop-database", str(omop_db)]
    if skip_clean:
        args.append("--skip-clean")

    _run(_BASE_DIR / "src" / "scripts" / "regenerate_data_pipeline.py", args)
    logger.info("Stage 2 complete.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Full DeepPhe pipeline: raw NLP output → compressed DB → OMOP DB → extracted concepts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # -------------------------------------------------------------------------
    # Stage selection
    # -------------------------------------------------------------------------
    parser.add_argument(
        "--skip-stage0",
        action="store_true",
        help="Skip Stage 0 (loader). Use when deepphe_sqlite_compressed already exists.",
    )
    parser.add_argument(
        "--skip-stage1",
        action="store_true",
        help="Skip Stage 1 (OMAP importer). Use when deepphe.sqlite3 already exists.",
    )
    parser.add_argument(
        "--only-stage0",
        action="store_true",
        help="Run Stage 0 only, then stop.",
    )
    parser.add_argument(
        "--only-stage1",
        action="store_true",
        help="Run up to and including Stage 1, then stop (implies --skip-stage0 is not set).",
    )

    # -------------------------------------------------------------------------
    # Stage 0 options
    # -------------------------------------------------------------------------
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory of raw DeepPhe NLP output files to load (Stage 0).",
    )
    input_group.add_argument(
        "--input-zip",
        type=Path,
        default=None,
        metavar="FILE",
        help="Single zip archive of DeepPhe output files to load (Stage 0).",
    )
    input_group.add_argument(
        "--input-zipdir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory tree of zip archives to load (Stage 0).",
    )
    parser.add_argument(
        "--compressed-db",
        type=Path,
        default=_DEFAULT_COMPRESSED_DB,
        metavar="PATH",
        help=(
            "Path to deepphe_sqlite_compressed — written by Stage 0, read by Stage 2 "
            f"(default: {_DEFAULT_COMPRESSED_DB})."
        ),
    )

    # -------------------------------------------------------------------------
    # Stage 1 options
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Stage 2 options
    # -------------------------------------------------------------------------
    parser.add_argument(
        "--omop-database",
        type=Path,
        default=_DEFAULT_OMOP_DB,
        metavar="PATH",
        help=(
            "Path to deepphe.sqlite3 — written by Stage 1, read by Stage 2 "
            f"(default: {_DEFAULT_OMOP_DB})."
        ),
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Pass --skip-clean to Stage 2 (do not delete existing extracted CSVs).",
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Validate: Stage 0 needs an input source unless being skipped
    # -------------------------------------------------------------------------
    running_stage0 = not args.skip_stage0
    if running_stage0 and not (args.input_dir or args.input_zip or args.input_zipdir):
        parser.error(
            "Stage 0 requires one of --input-dir, --input-zip, or --input-zipdir. "
            "Use --skip-stage0 to skip the loader stage."
        )

    logger.info("=" * 60)
    logger.info("DEEPPHE FULL PIPELINE")
    logger.info("Base directory: %s", _BASE_DIR)
    logger.info("=" * 60)

    compressed_db = args.compressed_db.resolve()
    omop_db = args.omop_database.resolve()

    # Stage 0
    if not args.skip_stage0:
        _run_stage0(
            input_dir=args.input_dir.resolve() if args.input_dir else None,
            input_zip=args.input_zip.resolve() if args.input_zip else None,
            input_zipdir=args.input_zipdir.resolve() if args.input_zipdir else None,
            compressed_db=compressed_db,
        )
        if args.only_stage0:
            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE (Stage 0 only)")
            logger.info("=" * 60)
            return 0

    # Stage 1
    if not args.skip_stage1:
        config = args.config.resolve()
        if not config.exists():
            logger.error("Config not found: %s", config)
            return 1
        _run_stage1(config, args.source_type)
        if args.only_stage1:
            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE (Stages 0–1)")
            logger.info("=" * 60)
            return 0

    # Stage 2
    _run_stage2(
        compressed_db=compressed_db,
        omop_db=omop_db,
        skip_clean=args.skip_clean,
    )

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
