# dphe-db-pipeline

[![tests](https://github.com/DeepPhe/dphe-db-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/DeepPhe/dphe-db-pipeline/actions/workflows/tests.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![License: Academic (DeepPhe)](https://img.shields.io/badge/license-Academic%20(DeepPhe)-lightgrey.svg)](LICENSE)

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

"Extractor" here means DeepPhe concept/phenotype extraction (the final analytics step),
not ETL-style extract-from-source — so it runs last, after the data is loaded and the OMOP
tables are built.

## OMOP source modes

Stage 2 reads demographics/diagnosis data from one of three sources, selected with
`--source-type`:

- `json` — patient demographics JSON (used by the bundled example).
- `csv` — source tables from a CSV directory.
- `mysql` — read-only source tables copied from MySQL into SQLite.

`csv` and `mysql` are configured through `.env`/environment variables. See
[docs/importer/](docs/importer/) for the importer architecture and configuration reference.

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

Boston Children's Hospital and University of Pittsburgh Academic Software Use Agreement
(DeepPhe Software). Academic, non-profit research use only — no redistribution, no
commercial use, and no clinical/diagnostic/treatment use. See [LICENSE](LICENSE) for the
full terms, attribution requirement, and third-party terms (HemOnc, NCIT).
