#!/usr/bin/env python3
"""
Generate per-patient structured summaries from the grouped SQLite tables.

Reads:
  - patient_id_mapping     (sequential_id <-> patient_id)
  - concepts_by_group      (bitmap-indexed concept rows)
  - attributes_by_group    (bitmap-indexed attribute rows)
  - cancers_by_group       (bitmap-indexed cancer rows)
  - tumors_by_group        (bitmap-indexed tumor rows)
  - omop_age_at_dx         (optional -- demographic lookup)
  - omop_gender            (optional)
  - omop_race              (optional)
  - omop_ethnicity         (optional)
  - omop_cancers           (optional)

Writes:
    output/extraction/data/patient_summaries.jsonl
  (one JSON object per line, one line per patient)
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from dphe_db_pipeline.extractor.patient_summaries.bitmap_index import (
    preload_attributes,
    preload_cancers,
    preload_concepts,
    preload_tumors,
)
from dphe_db_pipeline.extractor.patient_summaries.demographics import load_demographics
from dphe_db_pipeline.extractor.patient_summaries.models import (
    IndexedRow,
    PatientSummary,
    _hit_to_dict,
)
from dphe_db_pipeline.extractor.patient_summaries.postprocess import dedup_and_merge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_patient_id_mapping(conn: sqlite3.Connection) -> dict[int, str]:
    """Return {sequential_id: patient_id} from patient_id_mapping."""
    mapping: dict[int, str] = {}
    cur = conn.execute("SELECT sequential_id, patient_id FROM patient_id_mapping")
    for seq_id, patient_id in cur:
        mapping[int(seq_id)] = str(patient_id)
    return mapping


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _try_load_demographics(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, str | None]]:
    """Load demographics, returning empty dict if tables are absent."""
    required = ["omop_age_at_dx", "omop_gender", "omop_race", "omop_ethnicity", "omop_cancers"]
    missing = [t for t in required if not _table_exists(conn, t)]
    if missing:
        logger.warning(
            "Demographic tables not found (%s) -- demographics will be empty.",
            ", ".join(missing),
        )
        return {}
    try:
        return load_demographics(conn)
    except Exception as exc:
        logger.warning("Failed to load demographics: %s", exc)
        return {}


def _try_preload(
    conn: sqlite3.Connection,
    table: str,
    loader: Callable[[sqlite3.Connection], list[IndexedRow]],
) -> list[IndexedRow]:
    """Preload a bitmap index table, returning empty list if absent."""
    if not _table_exists(conn, table):
        logger.warning("Table '%s' not found -- skipping.", table)
        return []
    try:
        return loader(conn)
    except Exception as exc:
        logger.warning("Failed to preload %s: %s", table, exc)
        return []


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def build_summary(
    sequential_id: int,
    patient_id: str,
    demographics: dict[str, str | None],
    index_rows: list[IndexedRow],
) -> PatientSummary:
    """Build a PatientSummary by scanning all bitmap index rows for this patient."""
    summary = PatientSummary(
        patient_id=patient_id,
        sequential_id=sequential_id,
        demographics=demographics,
    )

    for row in index_rows:
        if sequential_id not in row.bitmap:
            continue
        hit = row.hit_factory(sequential_id)
        if hit is None:
            continue
        bucket_list = getattr(summary, hit.bucket, None)
        if bucket_list is None:
            bucket_list = summary.other_concepts
        bucket_list.append(_hit_to_dict(hit))

    return summary


def generate_patient_summaries(
    db_path: Path,
    output_path: Path,
) -> int:
    """
    Generate patient_summaries.jsonl.

    Returns:
        Number of patients written.
    """
    logger.info("Connecting to database: %s", db_path)
    conn = sqlite3.connect(str(db_path))

    try:
        if not _table_exists(conn, "patient_id_mapping"):
            logger.error(
                "patient_id_mapping table not found in %s. "
                "Run import_parsed_data.py first.",
                db_path,
            )
            return 0

        patient_map = _load_patient_id_mapping(conn)
        logger.info("Loaded %d patients from patient_id_mapping", len(patient_map))

        if not patient_map:
            logger.warning("patient_id_mapping is empty -- nothing to generate.")
            return 0

        # Load demographics (optional)
        demographics_map = _try_load_demographics(conn)

        # Preload all bitmap index tables
        logger.info("Preloading bitmap index tables...")
        all_rows = []
        all_rows.extend(_try_preload(conn, "concepts_by_group", preload_concepts))
        all_rows.extend(_try_preload(conn, "attributes_by_group", preload_attributes))
        all_rows.extend(_try_preload(conn, "cancers_by_group", preload_cancers))
        all_rows.extend(_try_preload(conn, "tumors_by_group", preload_tumors))
        logger.info("Loaded %d total bitmap rows", len(all_rows))

        # Write JSONL
        output_path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(output_path, "w", encoding="utf-8") as out_file:
            for seq_id in sorted(patient_map):
                patient_id = patient_map[seq_id]
                demographics = demographics_map.get(seq_id, {})

                summary = build_summary(seq_id, patient_id, demographics, all_rows)
                summary = dedup_and_merge(summary)

                line = json.dumps(summary.to_dict(), ensure_ascii=False)
                out_file.write(line + "\n")
                written += 1

        logger.info("Wrote %d patient summaries to %s", written, output_path)
        return written

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    from dphe_db_pipeline.paths import DEFAULT_COMPRESSED_DB, DEFAULT_EXTRACTION_DATA_DIR

    default_out = DEFAULT_EXTRACTION_DATA_DIR / "patient_summaries.jsonl"

    parser = argparse.ArgumentParser(
        description="Generate per-patient summaries from grouped SQLite tables."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_COMPRESSED_DB,
        help=f"Path to the compressed DeepPhe SQLite database (default: {DEFAULT_COMPRESSED_DB}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_out,
        help=f"Output JSONL path (default: {default_out}).",
    )
    args = parser.parse_args()

    db_path: Path = args.database.resolve()
    output_path: Path = args.output.resolve()

    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return 1

    written = generate_patient_summaries(db_path, output_path)
    return 0 if written > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
