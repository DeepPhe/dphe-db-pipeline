#!/usr/bin/env python3
"""
General-purpose tumor query script using bitmap intersections.

Query patients with specific tumor types from tumors_by_group table.
"""

import argparse
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


def query_patients_with_tumors(
    db_path: str,
    tumor_types: list[str],
    operation: str = 'AND',
    negated: bool = False,
    uncertain: bool = False,
    historic: bool = False,
    verbose: bool = True
) -> list[str]:
    """
    Query patients with specified tumor types.

    Args:
        db_path: Path to SQLite database
        tumor_types: List of tumor classUri patterns to search for
        operation: 'AND' (all types) or 'OR' (any type)
        negated: Filter by negated status
        uncertain: Filter by uncertain status
        historic: Filter by historic status
        verbose: Print progress messages

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
            SELECT patient_bitmap, classUri
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
            if verbose:
                print(f"  No matches for: {tumor_type}")
            if operation == 'AND':
                conn.close()
                return []
            continue

        # Deserialize bitmaps for this tumor type
        tumor_bitmaps = [BitMap.deserialize(row[0]) for row in rows]

        # Union all bitmaps for this tumor type
        combined_bitmap = tumor_bitmaps[0]
        for bm in tumor_bitmaps[1:]:
            combined_bitmap |= bm

        bitmaps.append(combined_bitmap)

        if verbose:
            print(f"  Found {len(combined_bitmap)} patients with {tumor_type}")
            for row in rows:
                print(f"    - {row[1]}")

    if not bitmaps:
        if verbose:
            print("\nNo patients found with specified tumor types")
        conn.close()
        return []

    # Combine bitmaps based on operation
    if operation == 'AND':
        # Patients must have ALL tumor types
        result_bitmap = bitmaps[0]
        for bm in bitmaps[1:]:
            result_bitmap &= bm
    else:  # OR
        # Patients must have ANY tumor type
        result_bitmap = bitmaps[0]
        for bm in bitmaps[1:]:
            result_bitmap |= bm

    # Get sequential IDs from bitmap
    sequential_ids = list(result_bitmap)

    if not sequential_ids:
        if verbose:
            print(f"\nNo patients found with tumor types ({operation} operation)")
        conn.close()
        return []

    if verbose:
        print(f"\nFound {len(sequential_ids)} patients ({operation} operation)")

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


def list_tumor_types(db_path: str, pattern: str | None = None):
    """
    List all unique tumor classUri values in the database.

    Args:
        db_path: Path to SQLite database
        pattern: Optional pattern to filter results
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if pattern:
        query = "SELECT DISTINCT classUri FROM tumors_by_group WHERE classUri LIKE ? ORDER BY classUri"
        rows = cursor.execute(query, (f'%{pattern}%',)).fetchall()
    else:
        query = "SELECT DISTINCT classUri FROM tumors_by_group ORDER BY classUri"
        rows = cursor.execute(query).fetchall()

    conn.close()

    print(f"\n{'='*80}")
    print(f"TUMOR TYPES IN DATABASE{f' (filtered by: {pattern})' if pattern else ''}")
    print('='*80)

    for i, (classUri,) in enumerate(rows, 1):
        # Extract the last part of the URI for readability
        tumor_name = classUri.split('/')[-1] if '/' in classUri else classUri
        print(f"  {i:3}. {tumor_name}")
        print(f"       {classUri}")

    print(f"\nTotal: {len(rows)} tumor types")
    print('='*80)


def main() -> int:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='Query patients with specific tumor types using bitmap intersections',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find patients with BOTH Adenocarcinoma AND BreastLump
  python query_tumors.py Adenocarcinoma BreastLump

  # Find patients with EITHER Adenocarcinoma OR BreastLump
  python query_tumors.py Adenocarcinoma BreastLump --or

  # List all tumor types in database
  python query_tumors.py --list

  # List tumor types matching pattern
  python query_tumors.py --list --pattern Breast

  # Query with modifiers
  python query_tumors.py Adenocarcinoma --negated
        """
    )

    parser.add_argument(
        'tumor_types',
        nargs='*',
        help='Tumor type(s) to search for (partial match on classUri)'
    )

    parser.add_argument(
        '--or',
        action='store_true',
        dest='use_or',
        help='Use OR operation (any type) instead of AND (all types)'
    )

    parser.add_argument(
        '--negated',
        action='store_true',
        help='Filter for negated tumors'
    )

    parser.add_argument(
        '--uncertain',
        action='store_true',
        help='Filter for uncertain tumors'
    )

    parser.add_argument(
        '--historic',
        action='store_true',
        help='Filter for historic tumors'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all tumor types in database'
    )

    parser.add_argument(
        '--pattern',
        type=str,
        help='Pattern to filter tumor type list (use with --list)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='output/databases/individual/deepphe.sqlite3',
        help='Path to database (default: output/databases/individual/deepphe.sqlite3)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress messages'
    )

    args = parser.parse_args()

    # Resolve database path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parents[4] / db_path

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return 1

    # List mode
    if args.list:
        list_tumor_types(str(db_path), args.pattern)
        return 0

    # Query mode
    if not args.tumor_types:
        parser.print_help()
        return 1

    operation = 'OR' if args.use_or else 'AND'

    if not args.quiet:
        print("="*80)
        print(f"QUERY: Patients with {' {operation} '.join(args.tumor_types)} tumors")
        print("="*80)
        print(f"Database: {db_path}")
        print(f"Operation: {operation}")
        print(f"Modifiers: negated={args.negated}, uncertain={args.uncertain}, historic={args.historic}")
        print()

    patient_ids = query_patients_with_tumors(
        str(db_path),
        args.tumor_types,
        operation=operation,
        negated=args.negated,
        uncertain=args.uncertain,
        historic=args.historic,
        verbose=not args.quiet
    )

    if not args.quiet:
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)

    if patient_ids:
        print(f"Total patients: {len(patient_ids)}")
        print("\nPatient IDs:")
        for i, patient_id in enumerate(patient_ids, 1):
            print(f"  {i:3}. {patient_id}")
    else:
        print("No patients found matching the criteria")

    if not args.quiet:
        print("="*80)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
