#!/usr/bin/env python3
"""
Import patient_summaries.jsonl into SQLite as zstd-compressed JSON blobs.

Reads per-patient JSONL produced by generate_patient_summaries.py and stores
each raw JSON line in patient_summaries(summary_json), keyed by the
sequential_id from patient_id_mapping.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path

import zstandard as zstd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)-8s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def resolve_paths(
    db_path: Path | None = None,
    jsonl_path: Path | None = None,
    data_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve DB and JSONL paths using explicit args or repo conventions."""
    from dphe_db_pipeline.paths import DEFAULT_COMPRESSED_DB, DEFAULT_EXTRACTION_DATA_DIR

    resolved_data_dir = data_dir or DEFAULT_EXTRACTION_DATA_DIR
    resolved_db_path = db_path or DEFAULT_COMPRESSED_DB
    resolved_jsonl_path = jsonl_path or (resolved_data_dir / "patient_summaries.jsonl")
    return resolved_db_path, resolved_jsonl_path


def recreate_patient_summaries_table(conn: sqlite3.Connection) -> None:
    """Drop and recreate patient_summaries table and index."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS patient_summaries;
        CREATE TABLE patient_summaries (
            patient_id INTEGER PRIMARY KEY,
            summary_json BLOB NOT NULL
        );
        CREATE INDEX idx_patient_summaries_patient_id ON patient_summaries(patient_id);
        """
    )


def load_patient_id_mapping(conn: sqlite3.Connection) -> dict[str, int]:
    """Load patient_id -> sequential_id mapping from patient_id_mapping table."""
    mapping: dict[str, int] = {}
    cursor = conn.execute("SELECT sequential_id, patient_id FROM patient_id_mapping")
    for sequential_id, patient_id in cursor:
        mapping[str(patient_id)] = int(sequential_id)
    return mapping


def import_patient_summaries(conn: sqlite3.Connection, jsonl_path: Path) -> int:
    """
    Import compressed patient summaries from JSONL into patient_summaries table.

    Returns:
        Number of rows imported.
    """
    patient_id_map = load_patient_id_mapping(conn)
    logger.info("Loaded patient_id_mapping with %d entries", len(patient_id_map))

    recreate_patient_summaries_table(conn)

    compressor = zstd.ZstdCompressor()
    imported_rows = 0
    with open(jsonl_path, encoding="utf-8") as jsonl_file:
        for line_number, line in enumerate(jsonl_file, start=1):
            if not line.strip():
                continue

            payload = json.loads(line)
            patient_id = str(payload.get("patient_id", "")).strip()
            sequential_id = patient_id_map.get(patient_id)

            if sequential_id is None:
                logger.warning(
                    "Skipping line %d: patient_id %r not found in patient_id_mapping",
                    line_number,
                    patient_id,
                )
                continue

            compressed_line = compressor.compress(line.encode("utf-8"))
            conn.execute(
                """
                INSERT INTO patient_summaries (patient_id, summary_json)
                VALUES (?, ?)
                """,
                (sequential_id, compressed_line),
            )
            imported_rows += 1

    logger.info("Imported %d row(s) into patient_summaries", imported_rows)
    return imported_rows


def run_import(db_path: Path, jsonl_path: Path) -> bool:
    """Execute import with transaction handling and rollback on failure."""
    if not db_path.exists():
        logger.error("Database file not found: %s", db_path)
        return False

    if not jsonl_path.exists():
        logger.error("JSONL file not found: %s", jsonl_path)
        return False

    conn = sqlite3.connect(str(db_path))
    try:
        import_patient_summaries(conn, jsonl_path)
        conn.commit()
        return True
    except Exception as exc:
        logger.error("Failed to import patient summaries: %s", exc, exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import output/extraction/data/patient_summaries.jsonl into SQLite."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to the target SQLite DB (default: output/databases/individual/deepphe.sqlite3).",
    )
    parser.add_argument(
        "--jsonl-path",
        type=Path,
        default=None,
        help="Path to patient_summaries.jsonl (default: <data-dir>/patient_summaries.jsonl).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Base extracted data dir used to derive default JSONL path.",
    )
    args = parser.parse_args()

    db_path, jsonl_path = resolve_paths(args.db_path, args.jsonl_path, args.data_dir)
    logger.info("Using database: %s", db_path)
    logger.info("Using JSONL: %s", jsonl_path)

    success = run_import(db_path, jsonl_path)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
