#!/usr/bin/env python3
"""
Investigate the actual filename structure to understand patient grouping
"""
import sqlite3
import sys
from collections import defaultdict


def investigate_structure(db_path: str) -> None:
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cursor = conn.cursor()

    print(f"Database: {db_path}\n")

    # Get total count
    cursor.execute('SELECT COUNT(*) FROM files')
    total = cursor.fetchone()[0]
    print(f"Total files: {total:,}\n")

    # Count files WITHOUT underscores
    cursor.execute("SELECT COUNT(DISTINCT filename) FROM files WHERE INSTR(filename, '_') = 0")
    no_underscore = cursor.fetchone()[0]
    print(f"Filenames WITHOUT underscores: {no_underscore}")

    # Count files WITH underscores
    cursor.execute("SELECT COUNT(DISTINCT filename) FROM files WHERE INSTR(filename, '_') > 0")
    with_underscore = cursor.fetchone()[0]
    print(f"Filenames WITH underscores: {with_underscore:,}\n")

    # Get sample filenames without underscores
    print("Sample filenames WITHOUT underscores:")
    cursor.execute("SELECT DISTINCT filename FROM files WHERE INSTR(filename, '_') = 0 ORDER BY filename LIMIT 10")
    samples_no_underscore = [row[0] for row in cursor.fetchall()]
    for i, fn in enumerate(samples_no_underscore, 1):
        print(f"  {i}. {fn}")

    # For each sample, find related files
    print("\n" + "="*80)
    print("Checking if files WITH underscores are related to files WITHOUT underscores:")
    print("="*80)

    for patient_id in samples_no_underscore[:3]:  # Check first 3
        print(f"\nPatient ID: {patient_id}")

        # Count files that start with this patient ID
        cursor.execute("SELECT COUNT(*) FROM files WHERE filename LIKE ?", (patient_id + '_%',))
        related_count = cursor.fetchone()[0]
        print(f"  Files starting with '{patient_id}_': {related_count}")

        if related_count > 0:
            cursor.execute("SELECT filename FROM files WHERE filename LIKE ? ORDER BY filename LIMIT 5", (patient_id + '_%',))
            related = [row[0] for row in cursor.fetchall()]
            for fn in related:
                print(f"    - {fn}")

    # Now let's look at the structure of filenames WITH underscores
    print("\n" + "="*80)
    print("Analyzing structure of filenames WITH underscores:")
    print("="*80)

    cursor.execute("SELECT filename FROM files WHERE INSTR(filename, '_') > 0 ORDER BY filename LIMIT 20")
    samples_with = [row[0] for row in cursor.fetchall()]

    print("\nFirst 20 filenames WITH underscores:")
    for i, fn in enumerate(samples_with, 1):
        parts = fn.split('_')
        print(f"  {i}. {fn}")
        print(f"      Parts: {parts}")
        print(f"      First part (patient ID?): {parts[0]}")

    # Check if first parts are unique
    print("\n" + "="*80)
    print("Analyzing first part of filenames (before first underscore):")
    print("="*80)

    cursor.execute("SELECT filename FROM files WHERE INSTR(filename, '_') > 0")
    first_parts: defaultdict[str, int] = defaultdict(int)

    for (filename,) in cursor:
        first_part = filename.split('_')[0]
        first_parts[first_part] += 1

    print(f"\nTotal unique 'first parts': {len(first_parts):,}")
    print("\nTop 10 'first parts' by file count:")
    sorted_parts = sorted(first_parts.items(), key=lambda x: x[1], reverse=True)
    for i, (part, count) in enumerate(sorted_parts[:10], 1):
        print(f"  {i}. '{part}' - {count:,} files")

    # Alternative: Maybe patient ID is the entire filename before extension?
    print("\n" + "="*80)
    print("Alternative: Checking if we should group by filename without extension:")
    print("="*80)

    cursor.execute("SELECT filename FROM files ORDER BY filename LIMIT 10")
    for i, (filename,) in enumerate(cursor.fetchall(), 1):
        # Remove common extensions
        base = filename
        for ext in ['.json', '.txt', '.xml', '.csv']:
            if base.endswith(ext):
                base = base[:-len(ext)]
                break
        print(f"  {i}. Original: {filename}")
        print(f"      Base: {base}")

    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "output/databases/individual/deepphe.sqlite3"
    investigate_structure(db_path)
