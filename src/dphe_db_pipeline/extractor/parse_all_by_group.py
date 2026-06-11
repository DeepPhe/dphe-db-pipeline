#!/usr/bin/env python3
# ruff: noqa: E402
"""Generate grouped CSVs from extracted Stage 3 CSV shards."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dphe_db_pipeline.extractor.parsers.parse_attributes_by_group import (
    export_to_csv as export_attributes_to_csv,
)
from dphe_db_pipeline.extractor.parsers.parse_attributes_by_group import parse_attributes_csv_files
from dphe_db_pipeline.extractor.parsers.parse_cancers_by_group import (
    export_to_csv as export_cancers_to_csv,
)
from dphe_db_pipeline.extractor.parsers.parse_cancers_by_group import parse_cancers_csv_files
from dphe_db_pipeline.extractor.parsers.parse_concepts_by_group import (
    export_to_csv as export_concepts_to_csv,
)
from dphe_db_pipeline.extractor.parsers.parse_concepts_by_group import parse_concepts_csv_files
from dphe_db_pipeline.extractor.parsers.parse_tumors_by_group import (
    export_to_csv as export_tumors_to_csv,
)
from dphe_db_pipeline.extractor.parsers.parse_tumors_by_group import parse_tumors_csv_files
from dphe_db_pipeline.paths import DEFAULT_EXTRACTION_DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParserSpec:
    name: str
    shard_dir_name: str
    grouped_file_name: str
    parse: Callable[[Path], Any]
    export: Callable[[Any, Path], None]
    required: bool = True


PARSER_SPECS = (
    ParserSpec(
        "concepts",
        "extracted_concepts",
        "concepts_by_group.csv",
        parse_concepts_csv_files,
        export_concepts_to_csv,
    ),
    ParserSpec(
        "attributes",
        "extracted_attributes",
        "attributes_by_group.csv",
        parse_attributes_csv_files,
        export_attributes_to_csv,
        required=False,
    ),
    ParserSpec(
        "cancers",
        "extracted_cancers",
        "cancers_by_group.csv",
        parse_cancers_csv_files,
        export_cancers_to_csv,
    ),
    ParserSpec(
        "tumors",
        "extracted_tumors",
        "tumors_by_group.csv",
        parse_tumors_csv_files,
        export_tumors_to_csv,
    ),
)


def parse_all_by_group(data_dir: Path) -> list[Path]:
    """Parse all extracted shard CSVs and return grouped CSVs that were written."""
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    missing_required: list[str] = []

    logger.info("=" * 80)
    logger.info("PARSING EXTRACTED CSV SHARDS")
    logger.info("=" * 80)
    logger.info("Data directory: %s", data_dir)

    for spec in PARSER_SPECS:
        shard_dir = data_dir / spec.shard_dir_name
        output_file = data_dir / spec.grouped_file_name
        logger.info("Parsing %s from %s", spec.name, shard_dir)

        try:
            grouped = spec.parse(shard_dir)
        except FileNotFoundError as exc:
            if spec.required:
                missing_required.append(str(exc))
                logger.error("%s", exc)
            else:
                logger.warning("%s; optional grouped CSV will not be created.", exc)
            continue

        spec.export(grouped, output_file)
        written.append(output_file)
        logger.info("Wrote %s", output_file)

    if missing_required:
        raise FileNotFoundError(
            "Required extracted CSV shards are missing:\n" + "\n".join(missing_required)
        )

    logger.info("=" * 80)
    logger.info("GROUPED CSV PARSING COMPLETE")
    logger.info("=" * 80)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate grouped CSVs from extracted CSV shards.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_EXTRACTION_DATA_DIR,
        help=f"Directory containing extracted CSV shards (default: {DEFAULT_EXTRACTION_DATA_DIR}).",
    )
    args = parser.parse_args()

    try:
        parse_all_by_group(args.data_dir)
    except Exception as exc:
        logger.error("Failed to parse grouped CSVs: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
