# dphe-db-pipeline

Full DeepPhe pipeline: raw NLP output → OMOP database → extracted concepts and patient summaries.

## Overview

This project extracts and processes medical concepts and cancer information from DeepPhe SQLite
databases. It queries the DeepPhe NLP output database, decompresses patient JSON records, parses
cancer/concept/tumor/attribute data, and exports structured results to CSV and JSONL for further
analysis or OMOP mapping.

The source databases are produced externally by the
[DeepPhe NLP pipeline](https://github.com/DeepPhe/DeepPhe-CR) and are not created by this project.

## Source Databases

Two SQLite databases are required as inputs:

| Database | Default path | Contents |
|---|---|---|
| `deepphe_sqlite_compressed` | `deepphe/deepphe_sqlite_compressed` | Per-patient `_Cancers.json` and `_Concepts.json` blobs (zstd-compressed). Primary extraction source. |
| `deepphe.sqlite3` | `deepphe/deepphe.sqlite3` | `CALCULATED_DX_DATA` and `CALCULATED_PATIENT_DATA` tables. Used for OMOP demographics (age, gender, race, ethnicity, cancer type). |

Both files are gitignored and must be placed in the `deepphe/` directory (or supplied via
`--database` / `--omop-database` flags).

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Set up the project

```bash
cd DeepPheConceptExtractor
uv sync            # create virtualenv and install dependencies
uv sync --all-extras  # include dev dependencies
```

## Usage

### Full pipeline (one command)

```bash
# Uses default database paths (deepphe/deepphe_sqlite_compressed)
python3 src/extractor/regenerate_data_pipeline.py

# Explicit database paths
python3 src/extractor/regenerate_data_pipeline.py \
  --database /path/to/deepphe_sqlite_compressed \
  --omop-database /path/to/deepphe.sqlite3

# Skip cleanup of previously generated CSVs
python3 src/extractor/regenerate_data_pipeline.py --skip-clean
```

The pipeline runs these steps in order:

1. `src/extractor/extractors/extract_cancers_data.py` - extract cancer/concept/tumor/attribute CSVs
2. `src/extractor/parse_all_by_group.py` - group extracted CSVs by DeepPhe group
3. `src/extractor/import_parsed_data.py` - import grouped CSVs into SQLite
4. `src/extractor/generate_patient_summaries.py` - build per-patient JSONL summaries
5. `src/extractor/import_patient_summaries.py` - import JSONL into SQLite

### Step-by-step

Each script accepts a `--database` option. All default to the paths under `deepphe/`.

```bash
# Extract cancer/concept/tumor/attribute data from deepphe_sqlite_compressed
python3 src/extractor/extractors/extract_cancers_data.py --database /path/to/deepphe_sqlite_compressed

# Parse and group extracted CSVs (no database needed)
python3 src/extractor/parse_all_by_group.py

# Import grouped CSVs back into SQLite
python3 src/extractor/import_parsed_data.py --database /path/to/deepphe_sqlite_compressed

# Extract OMOP demographics from deepphe.sqlite3
python3 src/extractor/extract_calculated_dx_data.py --database /path/to/deepphe.sqlite3
python3 src/extractor/extract_calculated_patient_data.py --database /path/to/deepphe.sqlite3

# Import patient summaries
python3 src/extractor/import_patient_summaries.py --db-path /path/to/deepphe_sqlite_compressed
```

## Project Structure

```
DeepPheConceptExtractor/
├── src/
│   ├── extractor/
│   │   ├── extractors/              # Extract raw data from source databases
│   │   │   └── extract_cancers_data.py
│   │   ├── parsers/                 # Parse and group extracted CSVs
│   │   ├── queries/                 # Ad-hoc query scripts
│   │   ├── patient_summaries/       # Patient summary generation
│   │   ├── regenerate_data_pipeline.py  # Full pipeline orchestrator
│   │   ├── parse_all_by_group.py
│   │   ├── import_parsed_data.py
│   │   ├── import_patient_summaries.py
│   │   ├── extract_calculated_dx_data.py
│   │   └── extract_calculated_patient_data.py
│   ├── analysis/                    # Analysis and reporting scripts
│   └── utils/                       # Utility helpers
├── deepphe/                         # Source databases (gitignored)
│   ├── deepphe_sqlite_compressed    # Primary DeepPhe NLP output
│   └── deepphe.sqlite3              # OMOP demographics
├── extracted_cancer_data/           # Pipeline output (gitignored)
├── tests/                           # Human-owned tests
├── .ai/
│   ├── md/                          # AI-generated documentation
│   ├── tests/                       # AI-generated tests
│   └── checks/                      # AI-generated checks
├── pyproject.toml
└── README.md
```

## Output

All output is written to `extracted_cancer_data/` (gitignored):

| File/Directory | Contents |
|---|---|
| `extracted_cancer_data/extracted_cancers/` | Per-shard cancer CSV files |
| `extracted_cancer_data/extracted_tumors/` | Per-shard tumor CSV files |
| `extracted_cancer_data/extracted_attributes/` | Per-shard attribute CSV files |
| `extracted_cancer_data/extracted_concepts/` | Per-shard concept CSV files |
| `extracted_cancer_data/cancers_by_group.csv` | Cancers grouped by DeepPhe group |
| `extracted_cancer_data/tumors_by_group.csv` | Tumors grouped by DeepPhe group |
| `extracted_cancer_data/attributes_by_group.csv` | Attributes grouped by name |
| `extracted_cancer_data/concepts_by_group.csv` | Concepts grouped by DeepPhe group |
| `extracted_cancer_data/omop_age_at_dx.csv` | Patient counts by age at diagnosis |
| `extracted_cancer_data/omop_cancers.csv` | Patient counts by cancer type |
| `extracted_cancer_data/omop_gender.csv` | Patient counts by gender |
| `extracted_cancer_data/omop_race.csv` | Patient counts by race |
| `extracted_cancer_data/omop_ethnicity.csv` | Patient counts by ethnicity |
| `extracted_cancer_data/patient_summaries.jsonl` | Per-patient structured summaries |

## Development

### Run tests

```bash
uv run pytest
```

### Type checking

```bash
uv run mypy src/
```

### Linting

```bash
uv run ruff check src/
uv run ruff format src/
```

## Requirements

- Python 3.11+
- DeepPhe SQLite databases (produced by the DeepPhe NLP pipeline)
- `zstandard` library for zstd-compressed database content

## Security Note

The source databases and all extracted output may contain protected health information (PHI).
They are gitignored and must never be committed to version control.

## License

[Add license information]
