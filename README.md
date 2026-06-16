# dphe-db-pipeline

DeepPhe pipeline for loading raw NLP output, building an OMOP SQLite database, and extracting cancer concepts and patient summaries.

## Requirements

- Python >=3.12
- [uv](https://github.com/astral-sh/uv)

```bash
uv sync
```

Development tools (`pytest`, `mypy`, `ruff`) are in the default dependency group and are
installed by `uv sync`. Use `uv sync --extra mysql` when you need MySQL ingestion support.

## Quickstart

Run the bundled example data:

```bash
uv run dphe-pipeline
```

This uses:

- DeepPhe example output: `src/dphe_db_pipeline/resources/example/dphe_output`
- OMOP demographics JSON: `src/dphe_db_pipeline/resources/example/omop_data/patient_demographics.json`
- OMOP importer config: `src/dphe_db_pipeline/omop_importer/omop-config.js`

Default outputs, relative to the directory where you run the command:

- DeepPhe SQLite DB: `output/databases/individual/deepphe.sqlite3`
- OMOP SQLite DB: `output/databases/individual/omop.sqlite3`
- Extraction output: `output/extraction/data/`

## Pipeline Stages

| Stage | Purpose | Default output |
|---|---|---|
| Stage 1 - Loader | Load raw DeepPhe JSON files, zip files, or zip directories into SQLite. | `output/databases/individual/deepphe.sqlite3` |
| Stage 2 - OMOP Importer | Import demographics/diagnosis data from JSON, CSV, or MySQL into OMOP-derived tables. | `output/databases/individual/omop.sqlite3` |
| Stage 3 - Extractor | Build grouped concept CSVs and patient summaries from the Stage 1 and Stage 2 databases. | `output/extraction/data/` |

## Common Commands

Run the full pipeline against a DeepPhe output directory:

```bash
uv run dphe-pipeline \
  --input-dir /path/to/deepphe/output \
  --omop-config src/dphe_db_pipeline/omop_importer/omop-config.js
```

Run against one zip archive:

```bash
uv run dphe-pipeline \
  --input-zip /path/to/deepphe-output.zip \
  --omop-config src/dphe_db_pipeline/omop_importer/omop-config.js
```

Run against a directory tree of zip archives:

```bash
uv run dphe-pipeline \
  --input-zipdir /path/to/zips \
  --omop-config src/dphe_db_pipeline/omop_importer/omop-config.js
```

Run only the extractor when both databases already exist:

```bash
uv run dphe-pipeline --skip-loader --skip-importer
```

Show all CLI options:

```bash
uv run dphe-pipeline --help
```

## OMOP Source Configuration

Stage 2 supports three source modes:

- `json`: patient demographics JSON, also used by the bundled example.
- `csv`: source tables from a CSV directory.
- `mysql`: read-only source tables copied from MySQL into SQLite.

Use `--demographics /path/to/patient_demographics.json` for JSON mode, or set source variables in `.env`/environment for CSV and MySQL. See `docs/importer/` for the detailed importer runbook and configuration reference.

## Project Layout

```text
src/dphe_db_pipeline/
├── pipeline.py        # Main CLI orchestration
├── loader/            # Stage 1
├── omop_importer/     # Stage 2
├── extractor/         # Stage 3
├── analysis/          # Analysis/reporting helpers
└── resources/example/ # Bundled reproducible example data
```

Tests live in `tests/`. Generated databases and extracted files live under `output/` in the current working directory and are gitignored.

## Development

```bash
uv run pytest
uv run ruff check src/dphe_db_pipeline tests
uv run mypy src/dphe_db_pipeline
```

## Security

Databases and extracted outputs may contain protected health information (PHI). They are gitignored and must not be committed.

## License

Not specified yet.
