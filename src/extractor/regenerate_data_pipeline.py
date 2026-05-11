#!/usr/bin/env python3
"""
Regenerate extracted/grouped CSVs and re-import into SQLite in one command.

Pipeline:
1) Optional cleanup of generated CSV shards/grouped files
2) extractors/extract_cancers_data.py
3) parse_all_by_group.py
4) import_parsed_data.py
5) generate_patient_summaries.py
6) import_patient_summaries.py
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Iterable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _cleanup_generated_files(base_dir: Path) -> int:
    """Delete generated CSV shards/grouped files to avoid stale outputs."""
    roots = [
        "extracted_cancer_data",
        # Backward-compat cleanup for older path bug in extract_cancers_data.py
        "src/extracted_cancer_data",
    ]
    patterns = []
    for root in roots:
        patterns.extend(
            [
                f"{root}/extracted_attributes/extracted_attributes_*.csv",
                f"{root}/extracted_cancers/extracted_cancers_*.csv",
                f"{root}/extracted_tumors/extracted_tumors_*.csv",
                f"{root}/extracted_concepts/extracted_concepts_*.csv",
                f"{root}/attributes_by_group.csv",
                f"{root}/cancers_by_group.csv",
                f"{root}/tumors_by_group.csv",
                f"{root}/concepts_by_group.csv",
            ]
        )

    deleted = 0
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            if path.is_file():
                path.unlink()
                deleted += 1

    return deleted


def _run_step(base_dir: Path, script_path: Path, extra_args: list[str] | None = None) -> None:
    """Run one Python script and fail fast on error."""
    cmd = [sys.executable, str(script_path)] + (extra_args or [])
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=base_dir, check=True)


def _iter_steps(
    base_dir: Path,
    database: Path | None,
    omop_database: Path | None,
) -> Iterable[tuple[Path, list[str]]]:
    """Return ordered pipeline steps with their extra CLI args."""
    db_args = ["--database", str(database)] if database else []
    omop_args = ["--database", str(omop_database)] if omop_database else []

    yield base_dir / "src/extractor/extractors/extract_cancers_data.py", db_args
    yield base_dir / "src/extractor/parse_all_by_group.py", []
    yield base_dir / "src/extractor/import_parsed_data.py", db_args
    yield base_dir / "src/extractor/generate_patient_summaries.py", db_args
    yield base_dir / "src/extractor/import_patient_summaries.py", (
        ["--db-path", str(database)] if database else []
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate extracted/grouped data and import into SQLite."
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Do not delete existing generated CSV files before running.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=(
            "Path to the deepphe_sqlite_compressed database. "
            "Defaults to <repo>/deepphe/deepphe_sqlite_compressed."
        ),
    )
    parser.add_argument(
        "--omop-database",
        type=Path,
        default=None,
        help=(
            "Path to the omop.sqlite3 OMOP database (used for demographics). "
            "Defaults to <repo>/deepphe/omop.sqlite3."
        ),
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent.parent

    database: Path | None = args.database.resolve() if args.database else None
    omop_database: Path | None = args.omop_database.resolve() if args.omop_database else None

    if database is not None and not database.exists():
        logger.error("--database path not found: %s", database)
        return 1
    if omop_database is not None and not omop_database.exists():
        logger.error("--omop-database path not found: %s", omop_database)
        return 1

    logger.info("=" * 80)
    logger.info("REGENERATE DATA PIPELINE")
    logger.info("=" * 80)
    logger.info("Base directory: %s", base_dir)
    if database:
        logger.info("Database: %s", database)
    if omop_database:
        logger.info("OMOP database: %s", omop_database)

    if not args.skip_clean:
        removed = _cleanup_generated_files(base_dir)
        logger.info("Cleanup complete: deleted %d generated CSV file(s)", removed)
    else:
        logger.info("Skipping cleanup (--skip-clean)")

    for step, extra_args in _iter_steps(base_dir, database, omop_database):
        if not step.exists():
            logger.error("Required script not found: %s", step)
            return 1
        _run_step(base_dir, step, extra_args)

    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
