#!/usr/bin/env python3
"""
Script to check the encodings used in the files table.
"""

import sqlite3

db_path = "deepphe_100"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get unique encodings from files ending with _Concepts
query = """
SELECT encoding, COUNT(*) as count 
FROM files 
WHERE filename LIKE '%_Concepts.json'
GROUP BY encoding
ORDER BY count DESC
"""

cursor.execute(query)
results = cursor.fetchall()

print("Encodings used in _Concepts.json files:")
print("="*60)
for encoding, count in results:
    print(f"  {encoding or 'NULL'}: {count} file(s)")

# Show sample of files with problematic encoding
print("\n" + "="*60)
print("Sample files with each encoding:")
print("="*60)

for encoding, _ in results:
    print(f"\nEncoding: {encoding or 'NULL'}")
    cursor.execute("""
        SELECT filename 
        FROM files 
        WHERE filename LIKE '%_Concepts.json' AND encoding = ?
        LIMIT 3
    """, (encoding,))

    for row in cursor.fetchall():
        print(f"  - {row[0]}")

conn.close()

