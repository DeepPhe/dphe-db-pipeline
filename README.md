# DeepPhe Concept Extractor

Medical concept extraction from DeepPhe database.

## Overview

This project extracts and processes medical concepts and cancer information from a DeepPhe SQLite database. It provides tools to query, extract, and export structured medical data.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Set up the project

```bash
# Clone the repository
cd DeepPheConceptExtractor

# Create virtual environment and install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras
```

## Usage

After installation, the following command-line tools are available:

```bash
# Extract cancer information
uv run extract-cancers

# Extract concept information
uv run extract-concepts

# Explore database structure
uv run explore-db

# Create concepts table
uv run create-concepts-table
```

### Direct script usage

You can also run scripts directly using uv:

```bash
# Run extraction scripts
uv run python scripts/extract_cancers.py
uv run python scripts/extract_concepts.py
```

## Project Structure

```
DeepPheConceptExtractor/
├── src/
│   └── deepphe_concept_extractor/  # Main package
│       ├── core/                    # Core extraction logic
│       ├── db/                      # Database interaction
│       └── cli.py                   # Command-line interface
├── scripts/                         # Thin CLI wrappers
├── tests/                           # Human-owned tests
├── .ai/
│   ├── md/                          # AI-generated documentation
│   ├── tests/                       # AI-generated tests
│   └── checks/                      # AI-generated checks
├── data/                            # Database files (gitignored)
├── pyproject.toml                   # Project configuration
└── README.md                        # This file
```

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

## Database

The project expects a SQLite database file named `deepphe_100` in the root directory containing medical concept data from DeepPhe.

## Output

Extracted data is saved to:
- `extracted_cancers/` - Cancer information JSON files
- `extracted_concepts/` - Concept information JSON files

## Requirements

- Python 3.11+
- SQLite database with DeepPhe data
- zstandard library for compressed content

## License

[Add license information]
