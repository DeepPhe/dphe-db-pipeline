#!/usr/bin/env python3
"""
Script to extract the first 100 patients from the DeepPhe SQLite database
and save them to a smaller sample SQLite database.

Assumes filenames follow pattern: {patient_id}_{timestamp}_{rest}
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_SOURCE_DB = "output/databases/individual/deepphe.sqlite3"
DEFAULT_TARGET_DB = "output/databases/individual/deepphe_100.sqlite3"


def open_db(db_path: str, read_only: bool = False):
    """Open database with proper options."""
    if read_only:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    else:
        conn = sqlite3.connect(db_path)

    # Set pragmas for optimal performance
    conn.execute('PRAGMA cache_size = -512000')  # 512MB cache
    conn.execute('PRAGMA mmap_size = 2147483648')  # 2GB memory-mapped I/O
    conn.execute('PRAGMA temp_store = MEMORY')
    return conn


def ensure_schema(conn: sqlite3.Connection):
    """Ensure the files table exists with expected columns and indexes."""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS files (
            filename TEXT PRIMARY KEY,
            content BLOB NOT NULL,
            encoding TEXT NOT NULL DEFAULT 'raw'
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)')
    conn.commit()


def extract_100_patients(source_db_path: str, target_db_path: str):
    """
    Extract first 100 patients from source database and save to target database.

    Args:
        source_db_path: Path to source DeepPhe SQLite database
        target_db_path: Path to target database (will be created/overwritten)
    """
    print(f"Opening source database: {source_db_path}")
    source_conn = open_db(source_db_path, read_only=True)
    source_cursor = source_conn.cursor()

    # Step 1: First pass - get first 100 distinct patient IDs (first part before underscore)
    print("Pass 1: Identifying first 100 patient IDs...")
    print("(Extracting from first part of filenames before underscore or timestamp)")

    patient_list = []
    patient_ids_seen = set()

    # Extract distinct patient IDs from filenames
    # Pattern: patientID.json or patientID_timestamp_... -> extract patientID.json
    # We need to handle both cases where the file is "1000000001.json" and "1000000001_timestamp.json"
    source_cursor.execute('''
        SELECT DISTINCT
            CASE
                -- If filename has underscore, get part before first underscore
                WHEN INSTR(filename, '_') > 0 THEN
                    CASE
                        -- If the part before underscore doesn't end with .json, add it
                        WHEN SUBSTR(filename, INSTR(filename, '_') - 5, 5) = '.json'
                        THEN SUBSTR(filename, 1, INSTR(filename, '_') - 1)
                        -- Otherwise add .json extension
                        ELSE SUBSTR(filename, 1, INSTR(filename, '_') - 1) || '.json'
                    END
                -- If no underscore, ensure it ends with .json
                WHEN INSTR(filename, '.json') > 0 THEN filename
                ELSE filename || '.json'
            END as patient_id
        FROM files
        WHERE INSTR(filename, '_') > 0  -- Only look at files with underscores (actual data files)
        ORDER BY patient_id
        LIMIT 100
    ''')

    for (patient_id,) in source_cursor:
        patient_list.append(patient_id)
        patient_ids_seen.add(patient_id)
        if len(patient_list) <= 10 or len(patient_list) % 10 == 0:
            print(f"  Patient #{len(patient_list)}: {patient_id}")

    if not patient_list:
        print("\nERROR: No patient IDs found")
        print("This database might be empty or use an unexpected filename structure.")
        source_conn.close()
        return

    print(f"\nIdentified {len(patient_list)} distinct patient IDs")
    print(f"Sample patient IDs: {patient_list[:3]}")

    # Step 2: Second pass - use SQL to efficiently collect ALL files for those patient IDs
    print("\nPass 2: Collecting all files for these patients...")
    print("(Using SQL queries for efficient filtering)")

    files_to_copy = []

    # Build a SQL query with OR conditions for each patient
    # Patient ID is like "1000000001.json", we need to match "1000000001_*"
    # We'll do this in batches to avoid SQL query length limits
    batch_size = 10
    for i in range(0, len(patient_list), batch_size):
        batch = patient_list[i:i+batch_size]

        # Build WHERE clause: filename LIKE 'patientID_base_%'
        # where patientID_base is the patient ID without .json extension
        conditions = []
        params = []
        for patient_id in batch:
            # Remove .json extension to get base ID for matching
            if patient_id.endswith('.json'):
                base_id = patient_id[:-5]  # Remove .json
            else:
                base_id = patient_id

            # Match files that start with base_id followed by underscore
            conditions.append("filename LIKE ?")
            params.append(base_id + '_%')

        where_clause = " OR ".join(conditions)
        query = f"SELECT filename FROM files WHERE {where_clause}"

        source_cursor.execute(query, params)
        batch_files = [row[0] for row in source_cursor.fetchall()]
        files_to_copy.extend(batch_files)

        print(f"  Processed {min(i+batch_size, len(patient_list))}/{len(patient_list)} patients, collected {len(files_to_copy)} files so far...")

    print(f"\nFound {len(patient_list)} patients with {len(files_to_copy)} total files")
    print(f"First patient ID: {patient_list[0]}")
    print(f"Last patient ID: {patient_list[-1]}")

    # Step 2: Create target database
    print(f"\nCreating target database: {target_db_path}")
    target_db = Path(target_db_path)
    if target_db.exists():
        print(f"Warning: {target_db_path} already exists, dropping existing tables...")

    target_conn = sqlite3.connect(target_db_path)
    target_cursor = target_conn.cursor()

    # Drop existing files table to start fresh
    target_cursor.execute('DROP TABLE IF EXISTS files')
    target_conn.commit()

    # Set up target database with optimizations
    ensure_schema(target_conn)
    target_cursor.execute('PRAGMA journal_mode = WAL')
    target_cursor.execute('PRAGMA synchronous = NORMAL')
    target_cursor.execute('PRAGMA cache_size = -512000')
    target_cursor.execute('PRAGMA temp_store = MEMORY')

    # Step 3: Copy files for selected patients
    print(f"\nCopying {len(files_to_copy)} files...")
    target_conn.execute('BEGIN TRANSACTION')

    total_files = 0
    total_bytes = 0
    batch_size = 1000
    batch_data = []

    for filename in files_to_copy:
        # Fetch the actual file content
        source_cursor.execute(
            'SELECT content, encoding FROM files WHERE filename = ?',
            (filename,)
        )
        row = source_cursor.fetchone()
        if row:
            content, encoding = row
            batch_data.append((filename, content, encoding))
            total_bytes += len(content)

            # Insert in batches for better performance
            if len(batch_data) >= batch_size:
                target_cursor.executemany(
                    'INSERT INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                    batch_data
                )
                total_files += len(batch_data)
                batch_data = []
                print(f"  Copied {total_files:,}/{len(files_to_copy):,} files ({total_bytes:,} bytes)")

    # Insert remaining files
    if batch_data:
        target_cursor.executemany(
            'INSERT INTO files (filename, content, encoding) VALUES (?, ?, ?)',
            batch_data
        )
        total_files += len(batch_data)

    # Commit transaction
    target_conn.commit()

    # Step 4: Verify and report
    target_cursor.execute('SELECT COUNT(*) FROM files')
    final_count = target_cursor.fetchone()[0]

    print("\nExtraction complete!")
    print(f"  Total patients: {len(patient_list)}")
    print(f"  Total files copied: {final_count}")
    print(f"  Total data size: {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MB)")

    # Get database file size
    target_db_size = target_db.stat().st_size
    print(f"  Database file size: {target_db_size:,} bytes ({target_db_size / (1024**2):.2f} MB)")

    # Close connections
    source_conn.close()
    target_conn.close()

    print(f"\nNew database created: {target_db_path}")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        source_db = sys.argv[1]
        target_db = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TARGET_DB
    else:
        # Default paths
        source_db = DEFAULT_SOURCE_DB
        target_db = DEFAULT_TARGET_DB

    source_path = Path(source_db)
    if not source_path.exists():
        print(f"Error: Source database not found: {source_db}")
        sys.exit(1)

    try:
        extract_100_patients(str(source_path), target_db)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
