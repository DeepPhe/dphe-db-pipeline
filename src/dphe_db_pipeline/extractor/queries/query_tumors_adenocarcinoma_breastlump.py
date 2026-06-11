#!/usr/bin/env python3
"""
Query patients with both Adenocarcinoma and BreastLump tumors.

Demonstrates bitmap intersection using the patient_id_mapping table.
"""

import sqlite3
from pathlib import Path
from typing import Any

BitMap: Any
try:
    from pyroaring import BitMap
    BITMAP_AVAILABLE = True
except ImportError:
    BITMAP_AVAILABLE = False
    BitMap = None


def query_patients_with_tumor_types(
    db_path: str,
    tumor_types: list[str],
    negated: bool = False,
    uncertain: bool = False,
    historic: bool = False
) -> list[str]:
    """
    Query patients that have ALL specified tumor types.

    Args:
        db_path: Path to SQLite database
        tumor_types: List of tumor classUri patterns to search for
        negated: Filter by negated status
        uncertain: Filter by uncertain status
        historic: Filter by historic status

    Returns:
        List of original patient IDs
    """
    if not BITMAP_AVAILABLE:
        print("ERROR: pyroaring not installed. Install with: pip install pyroaring")
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    bitmaps = []

    for tumor_type in tumor_types:
        # Query for tumors matching this type
        query = """
            SELECT patient_bitmap
            FROM tumors_by_group
            WHERE classUri LIKE ?
              AND negated = ?
              AND uncertain = ?
              AND historic = ?
        """

        rows = cursor.execute(
            query,
            (f'%{tumor_type}%', negated, uncertain, historic)
        ).fetchall()

        if not rows:
            print(f"No matches found for tumor type: {tumor_type}")
            conn.close()
            return []

        # Deserialize bitmaps for this tumor type
        tumor_bitmaps = [BitMap.deserialize(row[0]) for row in rows]

        # Union all bitmaps for this tumor type (OR operation)
        # Multiple rows might exist for the same tumor type
        if len(tumor_bitmaps) == 1:
            combined_bitmap = tumor_bitmaps[0]
        else:
            combined_bitmap = tumor_bitmaps[0]
            for bm in tumor_bitmaps[1:]:
                combined_bitmap |= bm

        bitmaps.append(combined_bitmap)
        print(f"Found {len(combined_bitmap)} patients with {tumor_type}")

    # Intersect all tumor type bitmaps (AND operation)
    # Patients must have ALL tumor types
    if len(bitmaps) == 0:
        conn.close()
        return []

    result_bitmap = bitmaps[0]
    for bm in bitmaps[1:]:
        result_bitmap &= bm

    # Get sequential IDs from bitmap
    sequential_ids = list(result_bitmap)

    if not sequential_ids:
        print("\nNo patients found with ALL specified tumor types")
        conn.close()
        return []

    print(f"\nFound {len(sequential_ids)} patients with ALL tumor types")

    # Convert sequential IDs to original patient IDs
    placeholders = ','.join('?' * len(sequential_ids))
    patient_rows = cursor.execute(f"""
        SELECT patient_id
        FROM patient_id_mapping
        WHERE sequential_id IN ({placeholders})
        ORDER BY sequential_id
    """, sequential_ids).fetchall()

    patient_ids = [row[0] for row in patient_rows]

    conn.close()
    return patient_ids


def main() -> None:
    """Main entry point."""
    base_dir = Path(__file__).resolve().parents[3]
    db_path = base_dir / "output" / "databases" / "individual" / "deepphe.sqlite3"

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return

    print("="*80)
    print("QUERY: Patients with Adenocarcinoma AND BreastLump tumors")
    print("="*80)
    print(f"Database: {db_path}\n")

    # Query for both tumor types
    tumor_types = ['Adenocarcinoma', 'BreastLump']

    patient_ids = query_patients_with_tumor_types(
        str(db_path),
        tumor_types,
        negated=False,
        uncertain=False,
        historic=False
    )

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    if patient_ids:
        print(f"Total patients: {len(patient_ids)}")
        print("\nPatient IDs:")
        for i, patient_id in enumerate(patient_ids, 1):
            print(f"  {i:3}. {patient_id}")

        # Show first 10 for preview
        if len(patient_ids) > 10:
            print(f"\n  ... and {len(patient_ids) - 10} more patients")
    else:
        print("No patients found matching the criteria")

    print("="*80)


if __name__ == "__main__":
    main()
