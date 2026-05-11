# DeepPheOutputLoader

A Python toolkit to load files from directories or zip archives into a SQLite database, where the key is the filename and the value is the (optionally compressed) file content.

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Load Files into SQLite

**Load all files from a directory recursively:**
```bash
python load_to_sqlite.py /path/to/input/files /path/to/database
```

**Load from a zip file:**
```bash
python load_to_sqlite.py /path/to/database --zip archive.zip
```

**Load from a directory of zip files (recursive):**
```bash
python load_to_sqlite.py /path/to/database --zipdir /path/to/zips
```

### Options

- `db_path`: Path where the SQLite database will be created/opened (required)
- `input_dir`: Directory containing files to load (optional, positional)
- `--zip`: Path to a single zip file to load
- `--zipdir`: Directory tree to scan for zip files; each zip's contents are added to the database
- `--no-recursive`: Do not recursively scan subdirectories (optional)

### Examples

**Load files recursively (default):**
```bash
python load_to_sqlite.py ./mydb ./data
```

**Load a single zip:**
```bash
python load_to_sqlite.py ./mydb --zip archive.zip
```

**Load all zips under a directory tree:**
```bash
python load_to_sqlite.py ./mydb --zipdir /path/to/zips
```

## How It Works

- The script scans the input directory (or zip archive) for files
- For each file:
  - **Key** (`filename`): Relative path from the input directory
  - **Value** (`content`): Complete file content, optionally compressed (zstd or lz4)
  - **Encoding**: Tracks whether content is `raw`, `zstd`, or `lz4`
- Files are stored in a SQLite database at the specified path
- Eight worker processes are used when loading from zip directories for maximum throughput
- A lock prevents concurrent writes so no data is lost

## Database Schema

```sql
CREATE TABLE files (
    filename TEXT PRIMARY KEY,
    content  BLOB NOT NULL,
    encoding TEXT NOT NULL DEFAULT 'raw'
)
```

Writing the same key twice simply overwrites the existing row (SQLite `INSERT OR REPLACE`).

## Querying the Database

Use `query_sqlite.py` to verify and retrieve data.

### Count total files
```bash
python query_sqlite.py count ./mydb
```

### List files
```bash
# First 10 (default)
python query_sqlite.py list ./mydb

# First 50
python query_sqlite.py list ./mydb --limit 50
```

### Retrieve a specific file
```bash
# Display content preview
python query_sqlite.py get ./mydb "path/to/file.json"

# Extract to disk
python query_sqlite.py get ./mydb "path/to/file.json" -o output.json
```

### Query by prefix
```bash
python query_sqlite.py prefix ./mydb "PATIENT_ID_"
```

## Extract a Sample Database

To extract the first 100 patients into a smaller SQLite database:

```bash
python extract_100_patients.py deepphe/deepphe_sqlite_compressed deepphe_100
```

See [EXTRACT_100_PATIENTS.md](EXTRACT_100_PATIENTS.md) for full details.

## Output

The load script provides a summary showing:
- Total files found
- Successfully loaded files
- Number of errors
- Total bytes loaded
- Database location
