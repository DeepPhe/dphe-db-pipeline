#!/usr/bin/env python3
"""
Check the actual number of distinct patients in a database
Patient IDs are filenames without underscores
"""
import sqlite3
import sys


def check_patients(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get distinct patient IDs (first part of filename before underscore, with .json)
    cursor.execute('''
        SELECT DISTINCT
            CASE
                -- If filename has underscore, get part before first underscore
                WHEN INSTR(filename, '_') > 0 THEN
                    CASE
                        -- If the part before underscore ends with .json, keep it
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
        WHERE INSTR(filename, '_') > 0  -- Only look at files with underscores
        ORDER BY patient_id
    ''')

    patient_ids = [row[0] for row in cursor.fetchall()]

    print(f"Database: {db_path}")
    print(f"Total unique patient IDs (with .json extension): {len(patient_ids)}")

    if patient_ids:
        print("\nFirst 10 patients:")
        for i, pid in enumerate(patient_ids[:10]):
            print(f"  {i+1}. {pid}")

        if len(patient_ids) > 10:
            print("\nLast 10 patients:")
            for i, pid in enumerate(patient_ids[-10:]):
                print(f"  {len(patient_ids)-9+i}. {pid}")
    else:
        print("\nNo patient IDs found")

    # Also show total files
    cursor.execute('SELECT COUNT(*) FROM files')
    total_files = cursor.fetchone()[0]
    print(f"\nTotal files in database: {total_files}")

    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "output/databases/individual/deepphe_100.sqlite3"
    check_patients(db_path)
