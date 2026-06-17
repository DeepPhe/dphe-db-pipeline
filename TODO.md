# TODO

Known issues flagged during code review (2026-06-17) but deferred. Each entry notes
the location, the problem, and a suggested fix.

## JSON importer commits once per row

`src/dphe_db_pipeline/omop_importer/source/json_demographics_processor.py`
(`_upsert_patient`, `_upsert_dx`)

Every patient triggers an `UPDATE` + conditional `INSERT` + `conn.commit()` per
table — O(n) commits. Fine for the bundled example (~500 rows) but slow at scale.

**Fix:** switch to `INSERT ... ON CONFLICT(PERSON_ID) DO UPDATE` and commit once
(or per N rows) outside the per-patient loop.

## CSV import: multiple processes write to one SQLite file

`src/dphe_db_pipeline/omop_importer/run.py` (`run_csv_import`, `mp.Pool(processes=2)`)

Worker processes each open their own connection and write to the same SQLite DB.
WAL permits only one writer, so writes serialize via `busy_timeout=30s` — correct,
but the parallelism only helps CSV parse/decode, not the inserts. Raising the worker
count increases write-lock contention without speeding up the writes.

**Fix:** if CSV import becomes a bottleneck, parse/transform in parallel but funnel
rows to a single writer (one process or one connection), instead of many processes
contending for the write lock.

## No end-to-end test for the CSV -> OMOP transform

`src/dphe_db_pipeline/omop_importer/run.py` (csv branch of `_run_omop_import`)

The CSV *ingestion* step is covered (`tests/omop_importer/test_csv_ingestion.py`), but
the full `--source-type csv` path — `change_column_types`, `add_lookup_tables`,
`create_columns` (incl. the `ICD` operation), `add_indexes`, `process_translation` —
has no automated test. It depends on source CSVs matching the view names in
`omop-config.js` plus `lookup_tables/SNOMED_CODES` and `ICD_CODES` directories, and
`SNOMED_CODES` is intentionally gitignored (too large).

**Fix:** build a minimal fixture set (tiny CSVs for the `*_VW` views + small SNOMED/ICD
lookup dirs + a trimmed config) and assert `CALCULATED_PATIENT_DATA` / `CALCULATED_DX_DATA`
are populated correctly. Heavyweight; worth it before changing the transform logic.

## process_a_csv_file writes process.log into the CWD

`src/dphe_db_pipeline/omop_importer/db/utils/csv_ops.py`

Every CSV import appends to a `process.log` file in the current working directory (no
path control) and emits progress via `print()` rather than `logging`.

**Fix:** drop the `process.log` side effect (or make the path configurable) and route
progress through the module logger.
