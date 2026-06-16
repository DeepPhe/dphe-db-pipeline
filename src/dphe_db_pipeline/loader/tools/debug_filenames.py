#!/usr/bin/env python3
"""
Debug script to see what filenames look like in the database
"""
import sqlite3
import sys


def debug_filenames(db_path: str) -> None:
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cursor = conn.cursor()

    print(f"Database: {db_path}\n")

    # Get total count
    cursor.execute('SELECT COUNT(*) FROM files')
    total = cursor.fetchone()[0]
    print(f"Total files: {total:,}\n")

    # Get first 20 filenames
    print("First 20 filenames:")
    cursor.execute('SELECT filename FROM files ORDER BY filename LIMIT 20')
    for i, (filename,) in enumerate(cursor.fetchall(), 1):
        has_underscore = '_' in filename
        print(f"  {i}. {filename} {'(has underscore)' if has_underscore else '(NO underscore)'}")

    # Count filenames without underscore using Python
    print("\nCounting filenames without underscores using Python...")
    cursor.execute('SELECT filename FROM files LIMIT 100000')
    no_underscore_count = 0
    no_underscore_samples: list[str] = []
    for (filename,) in cursor:
        if '_' not in filename:
            no_underscore_count += 1
            if len(no_underscore_samples) < 10:
                no_underscore_samples.append(filename)

    print(f"Found {no_underscore_count} filenames without underscores (in first 100K files)")
    if no_underscore_samples:
        print("\nSamples of filenames without underscores:")
        for sample in no_underscore_samples:
            print(f"  - {sample}")

    # Try the SQL query
    print("\nTrying SQL query: SELECT COUNT(*) FROM files WHERE filename NOT LIKE '%_%'")
    cursor.execute("SELECT COUNT(*) FROM files WHERE filename NOT LIKE '%_%'")
    sql_count = cursor.fetchone()[0]
    print(f"SQL query result: {sql_count}")

    # Try with INSTR instead
    print("\nTrying SQL query: SELECT COUNT(*) FROM files WHERE INSTR(filename, '_') = 0")
    cursor.execute("SELECT COUNT(*) FROM files WHERE INSTR(filename, '_') = 0")
    instr_count = cursor.fetchone()[0]
    print(f"INSTR query result: {instr_count}")

    # Get samples with INSTR
    print("\nGetting samples with INSTR query...")
    cursor.execute("SELECT filename FROM files WHERE INSTR(filename, '_') = 0 ORDER BY filename LIMIT 10")
    instr_samples = cursor.fetchall()
    print(f"Found {len(instr_samples)} samples:")
    for sample in instr_samples:
        print(f"  - {sample[0]}")

    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "output/databases/individual/deepphe.sqlite3"
    debug_filenames(db_path)
