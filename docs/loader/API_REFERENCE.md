# SQLite API Usage

This project uses Python's built-in `sqlite3` module to store files, with optional `zstd` or `lz4` compression for the content column.

## Basic Usage Example

```python
import sqlite3

# Open/create database
conn = sqlite3.connect("./mydb")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute('''
    CREATE TABLE IF NOT EXISTS files (
        filename TEXT PRIMARY KEY,
        content  BLOB NOT NULL,
        encoding TEXT NOT NULL DEFAULT 'raw'
    )
''')

# Insert a file (overwrites if key already exists)
conn.execute(
    "INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)",
    ("example.json", b'{"hello": "world"}', "raw")
)
conn.commit()

# Retrieve a file
row = conn.execute(
    "SELECT content, encoding FROM files WHERE filename = ?",
    ("example.json",)
).fetchone()
content, encoding = row
print(content)  # b'{"hello": "world"}'

# Check if a key exists
exists = conn.execute(
    "SELECT 1 FROM files WHERE filename = ?", ("example.json",)
).fetchone() is not None

# Delete a key
conn.execute("DELETE FROM files WHERE filename = ?", ("example.json",))
conn.commit()

# Count all rows
count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
print(f"Total files: {count}")

conn.close()
```

## Key Features

- **Standard library**: No extra dependencies — uses Python's built-in `sqlite3`
- **Optional compression**: Content stored as `raw`, `zstd`, or `lz4` bytes; encoding column tracks which
- **Upsert semantics**: `INSERT OR REPLACE` quietly overwrites duplicate keys
- **WAL mode**: Write-Ahead Logging enabled for better concurrent read performance

## Prefix Queries

```python
import sqlite3

conn = sqlite3.connect("./mydb")

# All files whose filename starts with a given prefix
prefix = "PATIENT_ID_"
rows = conn.execute(
    "SELECT filename FROM files WHERE filename LIKE ? || '%'",
    (prefix,)
).fetchall()

for (filename,) in rows:
    print(filename)

conn.close()
```

## Performance Tips

- Enable `PRAGMA cache_size = -524288` (512 MB cache)
- Enable `PRAGMA mmap_size = 17179869184` (16 GB memory-mapped I/O)
- Use `PRAGMA journal_mode = WAL` for concurrent reads
- Use `PRAGMA synchronous = NORMAL` for faster writes with reasonable safety
- Add an index on `filename` (already the PRIMARY KEY, so indexed by default)
- Batch inserts inside a single `BEGIN`/`COMMIT` transaction for bulk loads

## Testing

Run the query script to verify data inside the database:

```bash
python query_sqlite.py count ./mydb
python query_sqlite.py list  ./mydb --limit 20
python query_sqlite.py get   ./mydb "example.json"
```

## Installation

No extra packages required — `sqlite3` is part of the Python standard library.

For compression support:
```bash
pip install zstandard lz4
```
