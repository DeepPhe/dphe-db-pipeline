# Extract 100 Patients Script

## Overview
This script (`extract_100_patients.py`) extracts the first 100 patients from the `deepphe_sqlite_compressed` database and saves them to a new SQLite database named `deepphe_100`.

**Patient Identification**: Patient IDs are extracted from the **first part of filenames before the underscore**. For example:
- `1000000001_04022025183705.json` → Patient ID is `1000000001`
- `1000000001_04022025183705_M_1419.json` → Patient ID is `1000000001`
- `1000000001` (no underscore) → Patient ID is `1000000001`

All files with the same first part are grouped together as belonging to the same patient.

## How it works

1. **Pass 1 - Identify Patient IDs**: Uses an efficient SQL query to extract the first 100 distinct patient IDs (first part of filename before underscore):
   ```sql
   SELECT DISTINCT 
       CASE 
           WHEN INSTR(filename, '_') > 0 
           THEN SUBSTR(filename, 1, INSTR(filename, '_') - 1)
           ELSE filename
       END as patient_id
   FROM files 
   ORDER BY patient_id
   LIMIT 100
   ```

2. **Pass 2 - Collect All Files**: Uses efficient SQL queries to collect files for the 100 patient IDs. For each patient ID, queries for:
   - The patient ID file itself (`filename = 'patientID'`)
   - All files starting with that patient ID (`filename LIKE 'patientID_%'`)
   
   This is done in batches of 10 patients at a time to optimize SQL query performance.

3. **Batch Copy**: Fetches file content and copies all collected files in batches of 1000 for optimal performance.

4. **Preserves Compression**: The script maintains the same compression and encoding as the source database.

**Why Two Passes?**
- Pass 1 quickly identifies patient IDs by extracting distinct first parts from all filenames
- Pass 2 collects ALL files that belong to those patient IDs (exact match or starting with `patientID_`)
- This ensures complete data for each patient, regardless of how many files they have

## Usage

### Basic usage (uses default paths):
```bash
python3 extract_100_patients.py
```

This will:
- Read from: `deepphe/deepphe_sqlite_compressed`
- Write to: `deepphe_100`

### Custom paths:
```bash
python3 extract_100_patients.py <source_db> <target_db>
```

Example:
```bash
python3 extract_100_patients.py deepphe/deepphe_sqlite_compressed my_sample_db
```

### Using the shell script:
```bash
bash extract_100_patients.sh
```

## Output

The script provides progress updates:
- Shows the patient IDs being extracted
- Reports progress every 10 patients
- Shows total files, data size, and database file size at completion

Example output:
```
Opening source database: deepphe/deepphe_sqlite_compressed
Pass 1: Identifying first 100 patient IDs...
(Extracting from first part of filenames before underscore)
  Patient #1: 1000000001
  Patient #2: 1000000002
  ...
  Patient #10: 1000000010
  Patient #20: 1000000020
  ...
  Patient #100: 1000000100

Identified 100 distinct patient IDs

Pass 2: Collecting all files for these patients...
(Using SQL queries for efficient filtering)
  Processed 10/100 patients, collected 245 files so far...
  Processed 20/100 patients, collected 512 files so far...
  Processed 30/100 patients, collected 789 files so far...
  ...

Found 100 patients with 2543 total files
First patient ID: 1000000001
Last patient ID: 1000000100

Creating target database: deepphe_100

Copying 2543 files...
  Copied 1,000/2,543 files (15,234,567 bytes)
  Copied 2,000/2,543 files (31,456,789 bytes)
  Copied 2,543/2,543 files (156,789,012 bytes)

Extraction complete!
  Total patients: 100
  Total files copied: 2543
  Total data size: 156,789,012 bytes (149.56 MB)
  Database file size: 78,456,123 bytes (74.82 MB)

New database created: deepphe_100
```

## Verifying the Results

After extraction, you can verify the new database:

### Count files:
```bash
python3 query_sqlite.py count deepphe_100
```

### List files:
```bash
python3 query_sqlite.py list deepphe_100 --limit 20
```

### Query specific patient:
```bash
python3 query_sqlite.py prefix deepphe_100 "{patient_id}_"
```

### Get a specific file:
```bash
python3 query_sqlite.py get deepphe_100 "{filename}"
```

## Database Schema

The new database has the same schema as the source:

```sql
CREATE TABLE files (
    filename TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    encoding TEXT NOT NULL DEFAULT 'raw'
)
```

- `filename`: The full filename/key (e.g., "1000000001_04022025183705.json")
- `content`: The file content (compressed or raw bytes)
- `encoding`: Compression type ('raw', 'zstd', or 'lz4')

## Performance Notes

- **Two-pass approach with SQL optimization**: 
  - Pass 1: Fast SQL query to identify 100 patient IDs (< 1 minute)
  - Pass 2: SQL queries with OR conditions in batches of 10 patients (1-3 minutes)
- **Avoids Python loops**: Uses SQL's indexed queries instead of scanning 21+ million rows in Python
- **Dramatically faster**: Completes in minutes instead of hours
- Uses read-only mode for source database (safe, doesn't lock)
- Optimized with 512MB cache and memory-mapped I/O
- Copies files in batches of 1000 within a single transaction
- Progress updates every 100,000 files during scan and every 1,000 files during copy
- Efficient for large databases (150GB+) - typical runtime: 2-5 minutes depending on disk speed and database size

## Requirements

- Python 3.6+
- SQLite3 (built into Python)
- Source database must exist: `deepphe/deepphe_sqlite_compressed`

## Error Handling

The script will:
- Check if source database exists before starting
- Warn if target database already exists (will overwrite)
- Handle keyboard interrupts gracefully
- Print detailed error messages and stack traces if something goes wrong

