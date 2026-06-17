# Tests

Run the test suite from the project root:

```bash
uv run pytest
```

The suite covers the bundled example pipeline end to end, the Stage 1 loader input modes
(directory, zip, zip directory), the Stage 2 OMOP importer (JSON demographics, CSV ingestion,
and `.env`/config validation), extractor parser regressions and failure modes, and storage
helper behavior. Test fixtures live in `tests/resources/`.
