# Source Layout

The root `README.md` is the current user-facing guide. This file only documents the package layout under `src/`.

```text
src/
└── dphe_db_pipeline/
    ├── analysis/       # Reporting and exploratory scripts
    ├── extractor/      # Stage 3 - Extractor
    ├── loader/         # Stage 1 - Loader
    ├── omop_importer/  # Stage 2 - OMOP Importer
    ├── resources/      # Bundled example DeepPhe and OMOP data
    ├── paths.py        # Shared default paths
    ├── pipeline.py     # Packaged pipeline CLI
    └── utils/          # Shared utilities
```

Use `uv run dphe-pipeline` from the project root for the main CLI.
