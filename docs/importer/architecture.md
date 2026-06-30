# Architecture

This project imports, derives, and exports OMOP / DeepPhe-style cohort data.

## Core invariants

1. **SQLite is the only destination database.**
   - All writes go to `SQLITE_DB_PATH`.
   - The destination is a single SQLite file.
2. **`SOURCE_TYPE` only changes how data is read.**
   - `csv`: read source CSVs
   - `mysql`: read source tables from MySQL using `SELECT`
   - `json`: read structured demographics JSON
3. **MySQL is read-only.**
   - No schemas are created there.
   - No updates or inserts are written back to MySQL.
4. **JSON mode is reduced-scope.**
   - It populates calculated tables directly.
   - It skips steps that require imported source tables.

## Mental model

Think of the project as an ingestion adapter plus a config-driven transformation pipeline.

```text
CSV files / MySQL / JSON
        |
        v
   ingestion step
        |
        v
   SQLite destination
   ├── imported source tables   (csv/mysql only)
   ├── lookup tables            (ICD_CODES)
   └── calculated tables        (CALCULATED_*)
```

## High-level flow in `run.py`

`run.py` is the orchestration entrypoint.

1. Load runtime config from `.env` / environment variables
2. Open SQLite destination connections
3. Ingest data according to `SOURCE_TYPE`
4. Drop calculated tables for a fresh rebuild
5. Run config-driven pipeline steps when source tables exist
6. In JSON mode, populate calculated tables directly from JSON
7. Close all connections

## Flow by source mode

### `SOURCE_TYPE=csv`

- Read all `*.csv` files from `SOURCE_DIR`
- Import them into SQLite as source tables
- Run the full config-driven pipeline:
  - change column types
  - add pre-update indexes
  - build lookup tables
  - create/populate calculated columns and tables
  - add post-update indexes
  - translate concepts

### `SOURCE_TYPE=mysql`

- Connect to MySQL using the configured credentials
- Discover tables with `SHOW TABLES`
- For each table:
  - inspect columns with `SELECT * FROM table LIMIT 0`
  - stream rows with `SELECT * FROM table`
  - copy the table into SQLite
- Run the same full config-driven pipeline in SQLite

### `SOURCE_TYPE=json`

- Read a JSON file or directory of JSON files from `JSON_SOURCE_PATH`
- Normalize patient-level fields in `source/json_demographics_processor.py`
- Write directly to:
  - `CALCULATED_PATIENT_DATA`
  - `CALCULATED_DX_DATA`
- Skip source-table-dependent update/translation/index logic

## Logical table groups

### Imported source tables

These exist only in `csv` and `mysql` modes. Examples include:
- `DEMOGRAPHIC_BRCAOVCA_VW`
- `DEMOGRAPHIC_MELANOMA_VW`
- `DIAGNOSIS_BRCAOVCA_HOSP_VW`
- `DIAGNOSIS_MELANOMA_OUTPT_VW`
- `DEATH_BRCAOVCA_VW`

### Lookup tables

Static or derived reference tables such as:
- `ICD_CODES`

### Calculated tables

Primary downstream tables used by exports and reports:
- `CALCULATED_PATIENT_DATA`
- `CALCULATED_DX_DATA`
- `CALCULATED_PT_ICD_CODES`

## Important limitations

1. JSON mode is not a full substitute for source-table ingestion.
2. `omop-config.js` mostly describes the CSV/MySQL source-table pipeline.
3. `omop` and `lookup` in config are legacy logical group names, not separate destination databases.
4. Some legacy helper names still reflect an earlier MySQL-centric implementation, but writes now target SQLite.

## Code map

- `run.py` — orchestration and mode branching
- `source/config_processor.py` — config-driven table/column/index logic
- `source/json_demographics_processor.py` — JSON ingestion and normalization
- `db/omop/lookup_table_ops.py` — lookup table creation; `omop` is a legacy internal package name
- `db/omop/translate_ops.py` — concept translation logic
- `db/omop/icd_ops.py` — ICD-derived table logic
- `tools/export_tables.py` — export to delimited files
- `tools/` — ad hoc analysis, import/export, and reporting scripts
