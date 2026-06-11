#!/usr/bin/env python3
"""
End-to-end pipeline test using bundled test fixtures.

Stage 1: Load tests/resources/JSON_000000001.json.zip into deepphe_test (SQLite).
Stage 2: Import bundled example OMOP demographics JSON into deepphe_test.
Stage 3: Run the extractor pipeline against deepphe_test.

The Stage 3 extractor writes intermediate CSVs to a temporary data directory,
then imports the results back into deepphe_test.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEST_FIXTURES_DIR = _REPO_ROOT / "tests" / "resources"
_ZIP = _TEST_FIXTURES_DIR / "JSON_000000001.json.zip"
_DEMOGRAPHICS = (
    _REPO_ROOT
    / "src"
    / "dphe_db_pipeline"
    / "resources"
    / "example"
    / "omop_data"
    / "patient_demographics.json"
)


@pytest.fixture(autouse=True)
def _require_fixtures():
    if not _ZIP.exists():
        pytest.skip(f"Test fixture not found: {_ZIP}")
    if not _DEMOGRAPHICS.exists():
        pytest.skip(f"Test fixture not found: {_DEMOGRAPHICS}")


def test_full_pipeline(tmp_path):
    db_path = tmp_path / "deepphe_test"
    data_dir = tmp_path / "extraction_data"

    # ------------------------------------------------------------------
    # Stage 1: load raw DeepPhe zip into SQLite
    # ------------------------------------------------------------------
    from dphe_db_pipeline.loader.load_to_sqlite import load_files_to_db

    loaded, errors = load_files_to_db(
        input_dir=str(tmp_path),
        db_path=str(db_path),
        zip_file=str(_ZIP),
    )

    assert errors == 0, f"Stage 1: {errors} file(s) failed to load"
    assert loaded > 0, "Stage 1: no files were loaded from the zip"

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == loaded
    conn.close()

    # ------------------------------------------------------------------
    # Stage 2: import patient demographics (JSON mode) into deepphe_test
    # ------------------------------------------------------------------
    from dphe_db_pipeline.omop_importer.run import _open_sqlite
    from dphe_db_pipeline.omop_importer.source.json_demographics_processor import run_json_import

    conn = _open_sqlite(str(db_path))
    cursor = conn.cursor()
    run_json_import(str(_DEMOGRAPHICS), conn, cursor)
    cursor.close()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    pt_count = conn.execute("SELECT COUNT(*) FROM CALCULATED_PATIENT_DATA").fetchone()[0]
    dx_count = conn.execute("SELECT COUNT(*) FROM CALCULATED_DX_DATA").fetchone()[0]
    conn.close()

    assert "CALCULATED_PATIENT_DATA" in tables, "Stage 2: CALCULATED_PATIENT_DATA missing"
    assert "CALCULATED_DX_DATA" in tables, "Stage 2: CALCULATED_DX_DATA missing"
    assert pt_count > 0, "Stage 2: CALCULATED_PATIENT_DATA is empty"
    assert dx_count > 0, "Stage 2: CALCULATED_DX_DATA is empty"

    # ------------------------------------------------------------------
    # Stage 3: run the extractor pipeline
    # OMOP tables are in the same file as the NLP blobs so both --database
    # and --omop-database point to deepphe_test.
    # ------------------------------------------------------------------
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "src/dphe_db_pipeline/extractor/regenerate_data_pipeline.py"),
            "--database", str(db_path),
            "--omop-database", str(db_path),
            "--data-dir", str(data_dir),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Stage 3 failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Core grouped tables and patient summaries must be in deepphe_test.
    # attributes_by_group is only created when attribute data exists in the source.
    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    omop_counts = {
        name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in ("omop_age_at_dx", "omop_gender", "omop_race", "omop_ethnicity", "omop_cancers")
        if name in tables
    }
    conn.close()
    for table in ("concepts_by_group", "cancers_by_group", "tumors_by_group", "patient_summaries"):
        assert table in tables, f"Stage 3: expected table {table!r} missing from deepphe_test"
    for table in ("omop_age_at_dx", "omop_gender", "omop_race", "omop_ethnicity", "omop_cancers"):
        assert table in tables, f"Stage 3: expected table {table!r} missing from deepphe_test"
        assert omop_counts[table] > 0, f"Stage 3: expected table {table!r} to have rows"

    # Patient summaries JSONL must exist and be non-empty
    summaries_path = data_dir / "patient_summaries.jsonl"
    assert summaries_path.exists(), f"Stage 3: {summaries_path} was not written"
    lines = [ln for ln in summaries_path.read_text().splitlines() if ln.strip()]
    assert len(lines) > 0, "Stage 3: patient_summaries.jsonl is empty"

    # Spot-check: every line must be valid JSON with a patient_id
    for line in lines:
        record = json.loads(line)
        assert "patient_id" in record, f"Summary record missing patient_id: {line[:120]}"


def test_default_example_uses_bundled_omop_demographics():
    from dphe_db_pipeline.paths import DEFAULT_OMOP_DEMOGRAPHICS
    from dphe_db_pipeline.pipeline import _apply_default_example_omop, build_parser

    args = build_parser().parse_args([])
    assert args.demographics is None
    assert args.source_type is None

    _apply_default_example_omop(args)

    assert args.demographics == DEFAULT_OMOP_DEMOGRAPHICS
    assert args.source_type == "json"
