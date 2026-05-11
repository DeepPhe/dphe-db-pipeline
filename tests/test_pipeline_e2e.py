#!/usr/bin/env python3
"""
End-to-end pipeline test using bundled test fixtures.

Stage 0: Load test_resources/JSON_000000001.json.zip into deepphe_test (SQLite).
Stage 1: Import test_resources/patient_demographics.json (JSON mode) into deepphe_test.
Stage 2: Run the extractor pipeline against deepphe_test.

The Stage 2 extractor writes intermediate CSVs to extracted_cancer_data/ (repo
root, hardcoded), then imports the results back into deepphe_test.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEST_RESOURCES = _REPO_ROOT / "test_resources"
_ZIP = _TEST_RESOURCES / "JSON_000000001.json.zip"
_DEMOGRAPHICS = _TEST_RESOURCES / "patient_demographics.json"


@pytest.fixture(autouse=True)
def _require_fixtures():
    if not _ZIP.exists():
        pytest.skip(f"Test fixture not found: {_ZIP}")
    if not _DEMOGRAPHICS.exists():
        pytest.skip(f"Test fixture not found: {_DEMOGRAPHICS}")


def test_full_pipeline(tmp_path):
    db_path = tmp_path / "deepphe_test"

    # ------------------------------------------------------------------
    # Stage 0: load raw DeepPhe zip into SQLite
    # ------------------------------------------------------------------
    from src.loader.load_to_sqlite import load_files_to_db

    loaded, errors = load_files_to_db(
        input_dir=str(tmp_path),
        db_path=str(db_path),
        zip_file=str(_ZIP),
    )

    assert errors == 0, f"Stage 0: {errors} file(s) failed to load"
    assert loaded > 0, "Stage 0: no files were loaded from the zip"

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == loaded
    conn.close()

    # ------------------------------------------------------------------
    # Stage 1: import patient demographics (JSON mode) into deepphe_test
    # ------------------------------------------------------------------
    from src.omop_importer.run import _open_sqlite
    from src.omop_importer.source.json_demographics_processor import run_json_import

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

    assert "CALCULATED_PATIENT_DATA" in tables, "Stage 1: CALCULATED_PATIENT_DATA missing"
    assert "CALCULATED_DX_DATA" in tables, "Stage 1: CALCULATED_DX_DATA missing"
    assert pt_count > 0, "Stage 1: CALCULATED_PATIENT_DATA is empty"
    assert dx_count > 0, "Stage 1: CALCULATED_DX_DATA is empty"

    # ------------------------------------------------------------------
    # Stage 2: run the extractor pipeline
    # OMOP tables are in the same file as the NLP blobs so both --database
    # and --omop-database point to deepphe_test.
    # ------------------------------------------------------------------
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "src/extractor/regenerate_data_pipeline.py"),
            "--database", str(db_path),
            "--omop-database", str(db_path),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Stage 2 failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Core grouped tables and patient summaries must be in deepphe_test.
    # attributes_by_group is only created when attribute data exists in the source.
    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for table in ("concepts_by_group", "cancers_by_group", "tumors_by_group", "patient_summaries"):
        assert table in tables, f"Stage 2: expected table {table!r} missing from deepphe_test"

    # Patient summaries JSONL must exist and be non-empty
    summaries_path = _REPO_ROOT / "extracted_cancer_data" / "patient_summaries.jsonl"
    assert summaries_path.exists(), f"Stage 2: {summaries_path} was not written"
    lines = [ln for ln in summaries_path.read_text().splitlines() if ln.strip()]
    assert len(lines) > 0, "Stage 2: patient_summaries.jsonl is empty"

    # Spot-check: every line must be valid JSON with a patient_id
    for line in lines:
        record = json.loads(line)
        assert "patient_id" in record, f"Summary record missing patient_id: {line[:120]}"
