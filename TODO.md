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
