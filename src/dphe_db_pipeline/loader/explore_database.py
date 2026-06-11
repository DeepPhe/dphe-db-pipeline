#!/usr/bin/env python3
"""
Script to explore the deepphe_100 database structure.
"""

import sqlite3
from pathlib import Path


def main():
    """Main entry point."""
    base_dir = Path(__file__).resolve().parents[3]
    db_path = base_dir / "deepphe_100"

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return

    # Connect to the database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    print("Tables in database:")
    print("=" * 60)
    for table in tables:
        print(f"  - {table[0]}")

    # Get schema for 'files' table if it exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    if cursor.fetchone():
        print("\n" + "=" * 60)
        print("Schema for 'files' table:")
        print("=" * 60)
        cursor.execute("PRAGMA table_info(files)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")

        # Get count of files ending with _Concepts
        cursor.execute("SELECT COUNT(*) FROM files WHERE filename LIKE '%_Concepts'")
        count = cursor.fetchone()[0]
        print(f"\nFiles ending with '_Concepts': {count}")

        # Show sample filenames
        print("\n" + "=" * 60)
        print("Sample filenames ending with '_Concepts':")
        print("=" * 60)
        cursor.execute("SELECT filename FROM files WHERE filename LIKE '%_Concepts' LIMIT 5")
        for row in cursor.fetchall():
            print(f"  - {row[0]}")

    conn.close()


if __name__ == "__main__":
    main()
