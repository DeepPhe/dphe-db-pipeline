"""Top-level DeepPhe pipeline orchestration."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dphe_db_pipeline.loader.load_to_sqlite import load_files_to_db
from dphe_db_pipeline.omop_importer.run import run_omop_import
from dphe_db_pipeline.paths import (
    DEFAULT_COMPRESSED_DB,
    DEFAULT_EXTRACTION_DATA_DIR,
    DEFAULT_IMPORTER_CONFIG,
    DEFAULT_INPUT_DIR,
    DEFAULT_OMOP_DB,
    DEFAULT_OMOP_DEMOGRAPHICS,
    REPO_ROOT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _reset_sqlite_output(db_path: Path) -> None:
    """Remove an existing SQLite database and sidecar files before rebuilding it."""
    removed = False
    for candidate in (
        db_path,
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-journal"),
    ):
        if candidate.exists():
            candidate.unlink()
            removed = True

    if removed:
        logger.info("Removed existing Stage 1 SQLite output before rebuild: %s", db_path)


def _run_loader(
    input_dir: Path | None,
    input_zip: Path | None,
    input_zipdir: Path | None,
    compressed_db: Path,
) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 1 - Loader: building compressed DeepPhe SQLite DB")
    logger.info("=" * 60)

    compressed_db.parent.mkdir(parents=True, exist_ok=True)
    _reset_sqlite_output(compressed_db)

    if input_zip:
        loaded, errors = load_files_to_db(".", str(compressed_db), zip_file=str(input_zip))
    elif input_zipdir:
        loaded, errors = load_files_to_db(".", str(compressed_db), zipdir=str(input_zipdir))
    else:
        if input_dir is None:
            raise ValueError("Stage 1 requires an input directory, zip file, or zip directory.")
        loaded, errors = load_files_to_db(str(input_dir), str(compressed_db))

    if errors:
        raise RuntimeError(f"Stage 1 completed with {errors} file loading error(s).")
    if loaded == 0:
        raise RuntimeError("Stage 1 did not load any files.")

    logger.info("Stage 1 complete: loaded %d file(s).", loaded)


def _run_importer(
    config: Path,
    source_type: str | None,
    sqlite_db_path: Path,
    demographics: Path | None,
) -> None:
    logger.info("=" * 60)
    logger.info("STAGE 2 - OMOP importer: building OMOP SQLite DB (%s)", sqlite_db_path)
    logger.info("=" * 60)

    sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    run_omop_import(
        config,
        source_type=source_type,
        sqlite_db_path=sqlite_db_path,
        json_source_path=demographics,
    )
    logger.info("Stage 2 complete.")


def _run_extractor(
    compressed_db: Path,
    omop_db: Path,
    output_dir: Path,
    skip_clean: bool,
) -> None:
    from dphe_db_pipeline.extractor.regenerate_data_pipeline import run_regeneration

    logger.info("=" * 60)
    logger.info("STAGE 3 - Concept extractor")
    logger.info("=" * 60)

    run_regeneration(
        database=compressed_db,
        omop_database=omop_db,
        data_dir=output_dir,
        skip_clean=skip_clean,
    )
    logger.info("Stage 3 complete.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Full DeepPhe pipeline: raw NLP output -> compressed DB -> OMOP DB -> extracted concepts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--skip-loader",
        action="store_true",
        help="Skip Stage 1 loader. Use when deepphe.sqlite3 already exists.",
    )
    parser.add_argument(
        "--skip-importer",
        action="store_true",
        help="Skip Stage 2 OMOP importer. Use when the OMOP SQLite DB already exists.",
    )
    parser.add_argument(
        "--skip-extractor",
        action="store_true",
        help="Skip Stage 3 extractor.",
    )
    parser.add_argument(
        "--only-loader",
        action="store_true",
        help="Run Stage 1 loader only, then stop.",
    )
    parser.add_argument(
        "--only-importer",
        action="store_true",
        help="Run through Stage 2 OMOP importer, then stop.",
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        metavar="DIR",
        help=(
            "Directory of DeepPhe NLP output files to load in Stage 1 "
            f"(default: {DEFAULT_INPUT_DIR})."
        ),
    )
    input_group.add_argument(
        "--input-zip",
        type=Path,
        default=None,
        metavar="FILE",
        help="Single zip archive of DeepPhe output files to load in Stage 1.",
    )
    input_group.add_argument(
        "--input-zipdir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory tree of zip archives to load in Stage 1.",
    )
    parser.add_argument(
        "--compressed-db",
        type=Path,
        default=DEFAULT_COMPRESSED_DB,
        metavar="PATH",
        help=(
            "Path to the compressed DeepPhe SQLite DB written by Stage 1 and read by Stage 3 "
            f"(default: {DEFAULT_COMPRESSED_DB})."
        ),
    )

    parser.add_argument(
        "--omop-config",
        dest="omop_config",
        type=Path,
        default=DEFAULT_IMPORTER_CONFIG,
        help=f"Path to the OMOP importer config file (default: {DEFAULT_IMPORTER_CONFIG}).",
    )
    parser.add_argument(
        "--source-type",
        choices=("csv", "mysql", "json"),
        default=None,
        help="Override SOURCE_TYPE for Stage 2 (csv | mysql | json).",
    )
    parser.add_argument(
        "--demographics",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the Stage 2 OMOP demographics JSON file. Sets JSON_SOURCE_PATH. "
            "Defaults to bundled example OMOP JSON when using the bundled example input."
        ),
    )

    parser.add_argument(
        "--omop-database",
        type=Path,
        default=DEFAULT_OMOP_DB,
        metavar="PATH",
        help=(
            "Path to the OMOP SQLite DB written by Stage 2 and read by Stage 3 "
            f"(default: {DEFAULT_OMOP_DB})."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXTRACTION_DATA_DIR,
        metavar="DIR",
        help=(
            "Directory for Stage 3 CSVs and patient_summaries.jsonl "
            f"(default: {DEFAULT_EXTRACTION_DATA_DIR})."
        ),
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Pass --skip-clean to Stage 3 (do not delete existing extracted CSVs).",
    )
    return parser


def _uses_default_example_input(args: argparse.Namespace) -> bool:
    """Return True when Stage 1 is pointed at the bundled DeepPhe example output."""
    return (
        args.input_zip is None
        and args.input_zipdir is None
        and args.input_dir is not None
        and args.input_dir.resolve() == DEFAULT_INPUT_DIR.resolve()
    )


def _apply_default_example_omop(args: argparse.Namespace) -> None:
    """Use bundled OMOP JSON for the bundled DeepPhe example unless explicitly overridden."""
    if (
        not args.demographics
        and args.source_type is None
        and _uses_default_example_input(args)
    ):
        args.demographics = DEFAULT_OMOP_DEMOGRAPHICS
        args.source_type = "json"
        logger.info("Using bundled example OMOP demographics: %s", args.demographics)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    _apply_default_example_omop(args)

    if args.demographics and args.source_type is None:
        args.source_type = "json"

    if args.demographics and args.source_type != "json":
        parser.error("--demographics can only be used with --source-type json.")

    if not args.skip_loader and not (args.input_dir or args.input_zip or args.input_zipdir):
        parser.error(
            "Stage 1 requires one of --input-dir, --input-zip, or --input-zipdir. "
            "Use --skip-loader to skip the loader stage."
        )

    logger.info("=" * 60)
    logger.info("DEEPPHE FULL PIPELINE")
    logger.info("Base directory: %s", REPO_ROOT)
    logger.info("=" * 60)

    compressed_db = args.compressed_db.resolve()
    omop_db = args.omop_database.resolve()
    output_dir = args.output_dir.resolve()

    try:
        if not args.skip_loader:
            _run_loader(
                input_dir=args.input_dir.resolve() if args.input_dir else None,
                input_zip=args.input_zip.resolve() if args.input_zip else None,
                input_zipdir=args.input_zipdir.resolve() if args.input_zipdir else None,
                compressed_db=compressed_db,
            )
            if args.only_loader:
                logger.info("PIPELINE COMPLETE (Stage 1 only)")
                return 0

        if not args.skip_importer:
            config = args.omop_config.resolve()
            if not config.exists():
                raise FileNotFoundError(f"Config not found: {config}")
            _run_importer(
                config=config,
                source_type=args.source_type,
                sqlite_db_path=omop_db,
                demographics=args.demographics.resolve() if args.demographics else None,
            )
            if args.only_importer:
                logger.info("PIPELINE COMPLETE (Stage 1 and Stage 2)")
                return 0

        if not args.skip_extractor:
            _run_extractor(
                compressed_db=compressed_db,
                omop_db=omop_db,
                output_dir=output_dir,
                skip_clean=args.skip_clean,
            )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        return 1

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
