# DeepPheOutputLoader

A Python toolkit to load files from directories or zip archives into a SQLite database, where the key is the filename and the value is the (optionally compressed) file content.

## Installation

1. Install the project dependencies:

```bash
uv sync
```

## Usage

### Load Files into SQLite

**Load all files from a directory recursively:**
```bash
uv run python -m dphe_db_pipeline.loader.load_to_sqlite /path/to/input/files /path/to/database
```

**Load from a zip file:**
```bash
uv run python -m dphe_db_pipeline.loader.load_to_sqlite /path/to/database --zip archive.zip
```

**Load from a directory of zip files (recursive):**
```bash
uv run python -m dphe_db_pipeline.loader.load_to_sqlite /path/to/database --zipdir /path/to/zips
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
uv run python -m dphe_db_pipeline.loader.load_to_sqlite ./data ./mydb
```

**Load a single zip:**
```bash
uv run python -m dphe_db_pipeline.loader.load_to_sqlite ./mydb --zip archive.zip
```

**Load all zips under a directory tree:**
```bash
uv run python -m dphe_db_pipeline.loader.load_to_sqlite ./mydb --zipdir /path/to/zips
```

## How It Works

- The script scans the input directory (or zip archive) for files
- For each file:
  - **Key** (`filename`): Relative path from the input directory
  - **Value** (`content`): Complete file content, optionally compressed (zstd or lz4)
  - **Encoding**: Tracks whether content is `raw`, `zstd`, or `lz4`
- Files are stored in a SQLite database at the specified path
- Twelve worker processes are used by default when loading from zip directories
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

Use `dphe_db_pipeline.loader.query_sqlite` to verify and retrieve data.

### Count total files
```bash
uv run python -m dphe_db_pipeline.loader.query_sqlite count ./mydb
```

### List files
```bash
# First 10 (default)
uv run python -m dphe_db_pipeline.loader.query_sqlite list ./mydb

# First 50
uv run python -m dphe_db_pipeline.loader.query_sqlite list ./mydb --limit 50
```

### Retrieve a specific file
```bash
# Display content preview
uv run python -m dphe_db_pipeline.loader.query_sqlite get ./mydb "path/to/file.json"

# Extract to disk
uv run python -m dphe_db_pipeline.loader.query_sqlite get ./mydb "path/to/file.json" -o output.json
```

### Query by prefix
```bash
uv run python -m dphe_db_pipeline.loader.query_sqlite prefix ./mydb "PATIENT_ID_"
```

## Extract a Sample Database

To extract the first 100 patients into a smaller SQLite database:

```bash
uv run python -m dphe_db_pipeline.loader.extract_100_patients deepphe/deepphe_sqlite_compressed deepphe_100
```

See [EXTRACT_100_PATIENTS.md](EXTRACT_100_PATIENTS.md) for full details.

## Output

The load script provides a summary showing:
- Total files found
- Successfully loaded files
- Number of errors
- Total bytes loaded
- Database location
