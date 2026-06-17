#!/usr/bin/env python3
"""Regenerate extracted/grouped CSVs and re-import them into SQLite."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dphe_db_pipeline.paths import (
    DEFAULT_COMPRESSED_DB,
    DEFAULT_EXTRACTION_DATA_DIR,
    DEFAULT_OMOP_DB,
)

logger = logging.getLogger(__name__)

REQUIRED_GROUPED_CSVS = (
    "concepts_by_group.csv",
    "cancers_by_group.csv",
    "tumors_by_group.csv",
)


def _cleanup_generated_files(data_dir: Path) -> int:
    """Delete generated CSV shards/grouped files to avoid stale outputs."""
    patterns = [
        "extracted_attributes/extracted_attributes_*.csv",
        "extracted_cancers/extracted_cancers_*.csv",
        "extracted_tumors/extracted_tumors_*.csv",
        "extracted_concepts/extracted_concepts_*.csv",
        "attributes_by_group.csv",
        "cancers_by_group.csv",
        "tumors_by_group.csv",
        "concepts_by_group.csv",
        "patient_summaries.jsonl",
    ]

    deleted = 0
    for pattern in patterns:
        for path in data_dir.glob(pattern):
            if path.is_file():
                path.unlink()
                deleted += 1

    return deleted


def _validate_grouped_outputs(data_dir: Path) -> None:
    """Ensure required grouped CSVs exist before importing or summarizing."""
    missing = [name for name in REQUIRED_GROUPED_CSVS if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Required grouped CSV files were not produced: " + ", ".join(missing)
        )


def run_regeneration(
    database: Path = DEFAULT_COMPRESSED_DB,
    omop_database: Path = DEFAULT_OMOP_DB,
    data_dir: Path = DEFAULT_EXTRACTION_DATA_DIR,
    *,
    skip_clean: bool = False,
) -> None:
    """Run Stage 3 end to end for an existing DeepPhe and OMOP SQLite database pair."""
    from dphe_db_pipeline.extractor.extractors.extract_cancers_data import run_extraction
    from dphe_db_pipeline.extractor.generate_patient_summaries import generate_patient_summaries
    from dphe_db_pipeline.extractor.import_parsed_data import run_import as import_grouped_data
    from dphe_db_pipeline.extractor.import_patient_summaries import run_import as import_summaries
    from dphe_db_pipeline.extractor.parse_all_by_group import parse_all_by_group

    database = database.resolve()
    omop_database = omop_database.resolve()
    data_dir = data_dir.resolve()

    if not database.exists():
        raise FileNotFoundError(f"--database path not found: {database}")
    if not omop_database.exists():
        raise FileNotFoundError(f"--omop-database path not found: {omop_database}")

    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("REGENERATE DATA PIPELINE")
    logger.info("=" * 80)
    logger.info("Database: %s", database)
    logger.info("OMOP database: %s", omop_database)
    logger.info("Data directory: %s", data_dir)

    if skip_clean:
        logger.info("Skipping cleanup (--skip-clean)")
    else:
        removed = _cleanup_generated_files(data_dir)
        logger.info("Cleanup complete: deleted %d generated file(s)", removed)

    run_extraction(database, data_dir)
    parse_all_by_group(data_dir)
    _validate_grouped_outputs(data_dir)

    if not import_grouped_data(database, data_dir, omop_database):
        raise RuntimeError("Failed to import grouped CSV data into SQLite.")

    summaries_path = data_dir / "patient_summaries.jsonl"
    written = generate_patient_summaries(database, summaries_path)
    if written == 0:
        raise RuntimeError("Patient summary generation wrote zero rows.")

    if not import_summaries(database, summaries_path):
        raise RuntimeError("Failed to import patient summaries into SQLite.")

    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)-8s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
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
        default=DEFAULT_COMPRESSED_DB,
        help=f"Path to the compressed DeepPhe SQLite database (default: {DEFAULT_COMPRESSED_DB}).",
    )
    parser.add_argument(
        "--omop-database",
        type=Path,
        default=DEFAULT_OMOP_DB,
        help=f"Path to the omop.sqlite3 OMOP database (default: {DEFAULT_OMOP_DB}).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_EXTRACTION_DATA_DIR,
        help=f"Directory for Stage 3 intermediate and summary files (default: {DEFAULT_EXTRACTION_DATA_DIR}).",
    )
    args = parser.parse_args()

    try:
        run_regeneration(
            database=args.database,
            omop_database=args.omop_database,
            data_dir=args.data_dir,
            skip_clean=args.skip_clean,
        )
    except Exception as exc:
        logger.error("Stage 3 failed: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
