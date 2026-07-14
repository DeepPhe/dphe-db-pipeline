---
title: Quickstart
---

Install the project, run the full DeepPhe pipeline on the bundled example data, then
point it at your own data with a few common parameters.

## Requirements

- Python >=3.12
- [uv](https://github.com/astral-sh/uv)

## Install

```bash
uv sync
```

`uv sync` installs the runtime dependencies plus the development tools (`pytest`, `mypy`,
`ruff`), which live in the default dependency group. Add the MySQL source driver only if
you need `--source-type mysql`:

```bash
uv sync --extra mysql
```

## Run the default pipeline

```bash
uv run dphe-pipeline
```

With no arguments the pipeline runs all three stages against the bundled example data:

- DeepPhe NLP output: `src/dphe_db_pipeline/resources/example/dphe_output`
- OMOP demographics JSON: `src/dphe_db_pipeline/resources/example/omop_data/patient_demographics.json`
- OMOP importer config: `src/dphe_db_pipeline/omop_importer/omop-config.js`

Outputs are written relative to the directory you run the command from:

- Stage 1 DeepPhe SQLite DB: `output/databases/individual/deepphe.sqlite3`
- Stage 2 OMOP SQLite DB: `output/databases/individual/omop.sqlite3`
- Stage 3 extraction, including CSVs and `patient_summaries.jsonl`: `output/extraction/data/`

A successful run ends with `PIPELINE COMPLETE`. The `output/` tree is gitignored and can
be deleted and regenerated at any time.

## Common parameters for your own data

The default run takes no arguments because it uses the bundled example. When you point the
pipeline at real data, these are the parameters you will typically reach for. Run
`uv run dphe-pipeline --help` for the complete list.

### Choose the Stage 1 input

By default Stage 1 reads the bundled example directory. Override it with exactly one of:

| Parameter | Use for |
|---|---|
| `--input-dir DIR` | A directory of DeepPhe NLP output files. |
| `--input-zip FILE` | A single `.zip` archive of DeepPhe output. |
| `--input-zipdir DIR` | A directory tree of many `.zip` archives, loaded in parallel. |

```bash
uv run dphe-pipeline --input-dir /path/to/deepphe/output
```

:::tip
Selecting a non-default input also turns off the automatic bundled demographics, so you
must supply your own Stage 2 source with `--demographics` for JSON or `.env` for CSV/MySQL,
or pass `--skip-importer` if the OMOP database already exists.
:::

### Choose the Stage 2 OMOP source

| Parameter | Use for |
|---|---|
| `--source-type {json,csv,mysql}` | Which source the OMOP importer reads from. |
| `--demographics PATH` | Path to a demographics JSON file. Implies `--source-type json`. |
| `--omop-config PATH` | OMOP importer config (`.js` or `.json`). Defaults to the bundled `omop-config.js`. |

```bash
uv run dphe-pipeline \
  --input-dir /path/to/deepphe/output \
  --demographics /path/to/patient_demographics.json
```

`csv` and `mysql` sources are configured with `.env` or environment variables rather than
CLI flags. Copy the repository root
[`.env.example.importer`](https://github.com/DeepPhe/dphe-db-pipeline/blob/main/.env.example.importer)
to `.env` as a starting template, and see [Source modes](../importer/source-modes.md) for
details.

### Choose output locations

| Parameter | Default |
|---|---|
| `--compressed-db PATH` | `output/databases/individual/deepphe.sqlite3` for the Stage 1 DB. |
| `--omop-database PATH` | `output/databases/individual/omop.sqlite3` for the Stage 2 DB. |
| `--output-dir DIR` | `output/extraction/data/` for Stage 3 CSVs and summaries. |

### Run only some stages

| Parameter | Effect |
|---|---|
| `--skip-loader` | Skip Stage 1. Its database must already exist. |
| `--skip-importer` | Skip Stage 2. The OMOP database must already exist. |
| `--skip-extractor` | Skip Stage 3. |
| `--only-loader` | Run Stage 1, then stop. |
| `--only-importer` | Run Stages 1 and 2, then stop. |
| `--skip-clean` | Keep existing Stage 3 CSVs instead of deleting them first. |

```bash
# Re-run just the extractor against databases that already exist.
uv run dphe-pipeline --skip-loader --skip-importer
```

### Tolerate Stage 1 load errors

By default Stage 1 is strict: any file that fails to load aborts the run, so you never
build a database from a silently incomplete input set. When you knowingly have some bad or
unreadable files in a large batch and want the run to proceed anyway, raise the allowed
error fraction.

| Parameter | Default | Effect |
|---|---|---|
| `--max-load-error-fraction FRACTION` | `0.0` | Maximum fraction of Stage 1 files that may fail before the stage fails. `0` means fail on any error; `0.10` tolerates up to 10% failures; `1` ignores errors as long as at least one file loads. |

```bash
# Strict default: one unreadable file aborts the run.
uv run dphe-pipeline --input-zipdir /path/to/zips

# Lenient: tolerate up to 10% of input files failing to load.
uv run dphe-pipeline --input-zipdir /path/to/zips --max-load-error-fraction 0.10
```
