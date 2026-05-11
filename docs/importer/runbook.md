# Runbook

This is the operational guide for running, rerunning, and validating the importer.

## One-time setup

```bash
cd /Users/johnlevander/dev/omap-data-importer
cp .env.example .env
mkdir -p output/databases output/exported plots
uv sync
```

## Standard runs

### CSV mode

```bash
cd /Users/johnlevander/dev/omap-data-importer
SOURCE_DIR=/Volumes/4TB/oracle \
SQLITE_DB_PATH=output/databases/deepphe.sqlite3 \
uv run python run.py --config config.json --source-type csv
```

### MySQL mode

```bash
cd /Users/johnlevander/dev/omap-data-importer
SOURCE_TYPE=mysql \
SQLITE_DB_PATH=output/databases/deepphe.sqlite3 \
MYSQL_HOST=127.0.0.1 \
MYSQL_PORT=3306 \
MYSQL_USER=youruser \
MYSQL_PASSWORD=yourpassword \
MYSQL_DATABASE=omap \
uv run python run.py --config config.json --source-type mysql
```

### JSON mode

```bash
cd /Users/johnlevander/dev/omap-data-importer
JSON_SOURCE_PATH=/path/to/patient_demographics.json \
SQLITE_DB_PATH=output/databases/jsontest.sqlite3 \
uv run python run.py --config config.json --source-type json
```

## Rerun semantics

A rerun is destructive for calculated outputs.

`run.py` drops and rebuilds at least:
- `CALCULATED_DX_DATA`
- `CALCULATED_PT_ICD_CODES`
- `CALCULATED_PATIENT_DATA`
- `SNOMED_CODES`

Use a separate SQLite file if you want to preserve a previous run for comparison.

## Quick validation queries

### Show tables

```bash
sqlite3 output/databases/deepphe.sqlite3 ".tables"
```

### Count calculated rows

```bash
sqlite3 output/databases/deepphe.sqlite3 "SELECT COUNT(*) FROM CALCULATED_PATIENT_DATA;"
```

```bash
sqlite3 output/databases/deepphe.sqlite3 "SELECT COUNT(*) FROM CALCULATED_DX_DATA;"
```

### Sample patient rows

```bash
sqlite3 output/databases/deepphe.sqlite3 "SELECT PERSON_ID, GENDER, RACE, DATE_OF_BIRTH FROM CALCULATED_PATIENT_DATA LIMIT 10;"
```

### Sample diagnosis rows

```bash
sqlite3 output/databases/deepphe.sqlite3 "SELECT PERSON_ID, CANCER, AGE_AT_DX FROM CALCULATED_DX_DATA LIMIT 10;"
```

### Check JSON normalization results

```bash
sqlite3 output/databases/jsontest.sqlite3 "SELECT PERSON_ID, DATE_OF_BIRTH FROM CALCULATED_PATIENT_DATA WHERE DATE_OF_BIRTH IS NOT NULL LIMIT 10;"
```

```bash
sqlite3 output/databases/jsontest.sqlite3 "SELECT CANCER, COUNT(*) FROM CALCULATED_DX_DATA GROUP BY CANCER ORDER BY CANCER;"
```

## Export and reporting commands

### Export current calculated outputs

```bash
cd /Users/johnlevander/dev/omap-data-importer
uv run python export_tables.py
```

### Generate report outputs

```bash
cd /Users/johnlevander/dev/omap-data-importer
uv run python reports/icd_study.py
```

## Recommended re-entry path after time away

1. Read `README.md`
2. Read `docs/architecture.md`
3. Read `docs/config-reference.md`
4. Run a JSON-mode test into `output/databases/jsontest.sqlite3`
5. Inspect tables with `sqlite3`
6. Only then move on to CSV or MySQL source runs

## Safe scratch workflow

```bash
cd /Users/johnlevander/dev/omap-data-importer
rm -f output/databases/jsontest.sqlite3
JSON_SOURCE_PATH=/path/to/patient_demographics.json \
SQLITE_DB_PATH=output/databases/jsontest.sqlite3 \
uv run python run.py --config config.json --source-type json
sqlite3 output/databases/jsontest.sqlite3 ".tables"
```

