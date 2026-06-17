# dphe-db-pipeline

DeepPhe pipeline for loading raw NLP output, building an OMOP SQLite database, and
extracting cancer concepts and patient summaries.

## Getting started

Requires Python >=3.12 and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run dphe-pipeline   # runs the bundled example end to end
```

See [QUICKSTART.md](QUICKSTART.md) for installation details, the default run, and the
common CLI parameters for pointing the pipeline at your own data.

## Pipeline stages

| Stage | Purpose | Default output |
|---|---|---|
| Stage 1 — Loader | Load raw DeepPhe JSON files, zip files, or zip directories into SQLite. | `output/databases/individual/deepphe.sqlite3` |
| Stage 2 — OMOP importer | Import demographics/diagnosis data from JSON, CSV, or MySQL into OMOP-derived tables. | `output/databases/individual/omop.sqlite3` |
| Stage 3 — Extractor | Build grouped concept CSVs and patient summaries from the Stage 1 and Stage 2 databases. | `output/extraction/data/` |

## OMOP source modes

Stage 2 reads demographics/diagnosis data from one of three sources, selected with
`--source-type`:

- `json` — patient demographics JSON (used by the bundled example).
- `csv` — source tables from a CSV directory.
- `mysql` — read-only source tables copied from MySQL into SQLite.

`csv` and `mysql` are configured through `.env`/environment variables. See
[docs/importer/](docs/importer/) for the importer runbook and configuration reference.

## Project layout

```text
src/dphe_db_pipeline/
├── pipeline.py        # Main CLI orchestration
├── loader/            # Stage 1
├── omop_importer/     # Stage 2
├── extractor/         # Stage 3
├── analysis/          # Analysis/reporting helpers
└── resources/example/ # Bundled reproducible example data
```

Each stage keeps ad-hoc helper scripts under its own `tools/` subpackage. Tests live in
`tests/`. Generated databases and extracted files live under `output/` in the current
working directory and are gitignored.

## Development

```bash
uv run pytest
uv run ruff check src/dphe_db_pipeline tests
uv run mypy src/dphe_db_pipeline
```

## Security

Databases and extracted outputs may contain protected health information (PHI). They are
gitignored and must not be committed.

## License

Not specified yet.
