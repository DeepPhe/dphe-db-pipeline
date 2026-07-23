---
title: DeepPhe DB Pipeline
slug: /
---

DeepPhe DB Pipeline loads raw DeepPhe NLP output, builds SQLite databases for
pipeline and OMOP-style data, and extracts cancer concepts plus patient summary files
for downstream analysis and visualization.

## Start here

- [Quickstart](getting-started/quickstart.md) installs the project and runs the bundled
  example end to end.
- [DeepPhe input format](formats/deepphe-input.md) specifies the DeepPhe NLP output the
  pipeline expects, including the file naming rules extraction depends on.
- [OMOP input format](formats/omop-input.md) specifies the demographics and diagnosis data
  expected from JSON, CSV, or MySQL.
- [Output database](formats/output-database.md) documents every table in the
  `deepphe.sqlite3` database the pipeline produces.
- [Loader](loader/README.md) explains the Stage 1 SQLite loader for directories, zip
  files, and zip directories.
- [Source modes](importer/source-modes.md) explains how Stage 2 reads OMOP demographics
  data from JSON, CSV, or MySQL.
- [Architecture](importer/architecture.md) maps the importer flow and core invariants.
- [Standalone binary distribution](distribution.md) documents PyInstaller builds and CI
  release behavior.

## Pipeline stages

| Stage | Purpose | Default output |
|---|---|---|
| Stage 1 - Loader | Load raw DeepPhe JSON files, zip files, or zip directories into SQLite. | `output/databases/individual/deepphe.sqlite3` |
| Stage 2 - OMOP importer | Import demographics and diagnosis data from JSON, CSV, or MySQL into OMOP-derived tables. | `output/databases/individual/omop.sqlite3` |
| Stage 3 - Extractor | Build grouped concept CSVs and patient summaries from the Stage 1 and Stage 2 databases. | `output/extraction/data/` |

## Data safety

Databases and extracted outputs may contain protected health information (PHI). Generated
outputs are gitignored and should not be committed.
