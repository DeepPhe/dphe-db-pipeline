"""
OMOP demographic lookup -- small tables, scan once.
"""

from __future__ import annotations

import logging
import sqlite3

from pyroaring import BitMap

logger = logging.getLogger(__name__)


def _deserialize_bitmap(blob: bytes) -> BitMap:
    return BitMap.deserialize(blob)


def _build_omop_lookup(
    conn: sqlite3.Connection, table: str, value_col: str,
) -> dict[int, str]:
    """Return {sequential_id: value} for an omop_* table."""
    lookup: dict[int, str] = {}
    cur = conn.execute(f"SELECT {value_col}, patient_bitmap FROM {table}")
    for value, blob in cur:
        bm = _deserialize_bitmap(blob)
        for sid in bm:
            if sid not in lookup:
                lookup[sid] = str(value)
    return lookup


def load_demographics(conn: sqlite3.Connection) -> dict[int, dict[str, str | None]]:
    """Build demographics dict keyed by sequential_id."""
    logger.info("Loading OMOP demographic tables...")
    age_map = _build_omop_lookup(conn, "omop_age_at_dx", "age_at_dx")
    logger.info("  omop_age_at_dx: %d entries", len(age_map))

    gender_map = _build_omop_lookup(conn, "omop_gender", "gender")
    logger.info("  omop_gender: %d entries", len(gender_map))

    race_map = _build_omop_lookup(conn, "omop_race", "race")
    logger.info("  omop_race: %d entries", len(race_map))

    ethnicity_map = _build_omop_lookup(conn, "omop_ethnicity", "ethnicity")
    logger.info("  omop_ethnicity: %d entries", len(ethnicity_map))

    cancer_map = _build_omop_lookup(conn, "omop_cancers", "cancer")
    logger.info("  omop_cancers: %d entries", len(cancer_map))

    all_sids: set[int] = set()
    for m in (age_map, gender_map, race_map, ethnicity_map, cancer_map):
        all_sids.update(m.keys())

    demographics: dict[int, dict[str, str | None]] = {}
    for sid in all_sids:
        demographics[sid] = {
            "age_at_dx": age_map.get(sid),
            "gender": gender_map.get(sid),
            "race": race_map.get(sid),
            "ethnicity": ethnicity_map.get(sid),
            "cancer_type": cancer_map.get(sid),
        }
    logger.info("Demographics assembled for %d patients", len(demographics))
    return demographics
