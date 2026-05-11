# Troubleshooting

## `SOURCE_TYPE` is invalid

Symptom:
- startup fails or prints that `SOURCE_TYPE` must be one of `csv`, `mysql`, or `json`

Fix:
- check `.env`
- check one-off environment overrides
- check the `--source-type` CLI flag

## CSV run says `SOURCE_DIR` does not exist

Symptom:
- `run.py` prints an error about `SOURCE_DIR`

Fix:
- verify the path exists
- pass `SOURCE_DIR=/actual/path` inline for a one-off run
- ensure the directory contains `.csv` files

## MySQL run connects but no useful tables appear in SQLite

Symptom:
- MySQL connection succeeds, but downstream tables are missing

Fix:
- inspect the source database directly to confirm the expected tables exist
- confirm `MYSQL_DATABASE` points at the source schema you intend to copy
- remember that this code runs `SHOW TABLES` and then `SELECT *` per discovered table

## JSON run finishes but expected source tables are missing

Symptom:
- you only see `CALCULATED_*` tables after a JSON run

Explanation:
- this is expected
- JSON mode does not recreate imported source tables

## JSON run imports fewer rows than expected

Common causes:
- some records are missing `PatientID`
- the payload does not contain a top-level `patients` list
- duplicate `PatientID` values are being upserted into one row per patient

Checks:

```bash
sqlite3 output/databases/jsontest.sqlite3 "SELECT COUNT(*) FROM CALCULATED_PATIENT_DATA;"
```

```bash
sqlite3 output/databases/jsontest.sqlite3 "SELECT COUNT(*) FROM CALCULATED_DX_DATA;"
```

## Dates are missing in JSON mode

Symptom:
- `DATE_OF_BIRTH` is `NULL` for some imported patients

Explanation:
- JSON mode only normalizes recognized date formats
- supported values currently include `MM-DD-YYYY` and `YYYY-MM-DD`
- invalid values are set to `NULL`

## Cancer values are missing in JSON mode

Symptom:
- `CANCER` is `NULL`

Explanation:
- only recognized values map cleanly today:
  - `BreastCancer` -> `B`
  - `OvarianCancer` -> `O`
  - `Melanoma` -> `M`
- unrecognized values are stored as `NULL`

## Missing tables during reporting/export

Symptom:
- exports or reports fail because calculated tables do not exist

Fix:
- confirm you ran the correct source mode first
- confirm you are pointing at the correct `SQLITE_DB_PATH`
- inspect the destination DB with `.tables`

## The repo is hard to re-understand after time away

Recommended order:
1. `README.md`
2. `docs/architecture.md`
3. `docs/runbook.md`
4. `docs/config-reference.md`
5. `run.py`
6. `source/config_processor.py`

