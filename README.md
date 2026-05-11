# dphe-db-pipeline

Full DeepPhe pipeline: raw NLP output → OMOP database → extracted concepts and patient summaries.

## Overview

This project turns raw [DeepPhe NLP](https://github.com/DeepPhe/DeepPhe-CR) output files and
demographic/diagnosis source data into a structured SQLite database of extracted cancer concepts,
tumor attributes, and per-patient summaries.

## Pipeline Stages

| Stage | Script | Input | Output |
|---|---|---|---|
| 0 — Loader | `src/loader/` | Raw DeepPhe JSON output files (dir or zip) | `deepphe/deepphe_sqlite_compressed` |
| 1 — Importer | `src/importer/` | Demographics/diagnosis data (CSV, MySQL, or JSON) | `deepphe/deepphe.sqlite3` |
| 2 — Extractor | `src/extractor/` | Both databases above | CSVs + `patient_summaries.jsonl` in `extracted_cancer_data/` |

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is not installed
cd dphe-db-pipeline
uv sync                  # install dependencies
uv sync --all-extras     # include dev + mysql extras
```

## Usage

### Full pipeline (recommended)

```bash
# Input: directory of raw DeepPhe output + CSV demographics
python pipeline.py \
  --input-dir /path/to/deepphe/output \
  --config src/importer/config.json

# Input: zip archive of DeepPhe output
python pipeline.py \
  --input-zip /path/to/JSON_000000001.json.zip \
  --config src/importer/config.json

# Input: directory tree of zip archives
python pipeline.py \
  --input-zipdir /path/to/zips/ \
  --config src/importer/config.json
```

### Partial runs

```bash
# Stage 0 only (build deepphe_sqlite_compressed)
python pipeline.py --input-dir /path/to/deepphe/output --only-stage0

# Stages 0 + 1 only
python pipeline.py --input-dir /path/to/deepphe/output \
  --config src/importer/config.json --only-stage1

# Skip Stage 0 (deepphe_sqlite_compressed already built)
python pipeline.py --skip-stage0 --config src/importer/config.json

# Stage 2 only (both databases already exist)
python pipeline.py --skip-stage0 --skip-stage1
```

### Stage 0 — Loader

Loads raw DeepPhe JSON output files into `deepphe_sqlite_compressed` (zstd-compressed blobs keyed
by filename).

```bash
python src/loader/load_to_sqlite.py /path/to/deepphe/output deepphe/deepphe_sqlite_compressed
python src/loader/load_to_sqlite.py deepphe_db --zip /path/to/JSON_000000001.json.zip
python src/loader/load_to_sqlite.py deepphe_db --zipdir /path/to/zip/directory
```

### Stage 1 — Importer

Ingests demographic and diagnosis source data and builds `deepphe.sqlite3`
(`CALCULATED_PATIENT_DATA`, `CALCULATED_DX_DATA`, `CALCULATED_PT_ICD_CODES`).

```bash
python src/importer/run.py --config src/importer/config.json
python src/importer/run.py --config src/importer/config.json --source-type json
```

See `src/importer/config.json` and the importer README for configuration details.

### Stage 2 — Extractor

Reads both databases and produces extracted CSVs and per-patient JSONL summaries.

```bash
python src/extractor/regenerate_data_pipeline.py
python src/extractor/regenerate_data_pipeline.py \
  --database /path/to/deepphe_sqlite_compressed \
  --omop-database /path/to/deepphe.sqlite3
```

## Project Structure

```
dphe-db-pipeline/
├── pipeline.py                      # Top-level pipeline orchestrator (all 3 stages)
├── src/
│   ├── loader/                      # Stage 0: load raw DeepPhe output → SQLite
│   ├── importer/                    # Stage 1: ingest demographics → deepphe.sqlite3
│   └── extractor/                   # Stage 2: extract concepts → CSVs + JSONL
│       ├── extractors/              # Extract raw data from deepphe_sqlite_compressed
│       ├── parsers/                 # Group extracted CSVs by concept type
│       ├── patient_summaries/       # Per-patient summary generation
│       ├── queries/                 # Ad-hoc query scripts
│       └── regenerate_data_pipeline.py  # Stage 2 orchestrator
├── deepphe/                         # Databases (gitignored)
│   ├── deepphe_sqlite_compressed    # Built by Stage 0
│   └── deepphe.sqlite3              # Built by Stage 1
├── extracted_cancer_data/           # Stage 2 output (gitignored)
├── tests/
└── pyproject.toml
```

## Output

All output is written to `extracted_cancer_data/` (gitignored):

| File/Directory | Contents |
|---|---|
| `extracted_cancers/` | Per-shard cancer CSV files |
| `extracted_tumors/` | Per-shard tumor CSV files |
| `extracted_attributes/` | Per-shard attribute CSV files |
| `extracted_concepts/` | Per-shard concept CSV files |
| `cancers_by_group.csv` | Cancers grouped by DeepPhe class |
| `tumors_by_group.csv` | Tumors grouped by DeepPhe class |
| `attributes_by_group.csv` | Attributes grouped by name |
| `concepts_by_group.csv` | Concepts grouped by DeepPhe class |
| `patient_summaries.jsonl` | Per-patient structured summaries |

## Development

```bash
uv run pytest          # run tests
uv run mypy src/       # type checking
uv run ruff check src/ # linting
```

## Security Note

All databases and extracted output may contain protected health information (PHI).
They are gitignored and must never be committed to version control.

## License

[Add license information]
