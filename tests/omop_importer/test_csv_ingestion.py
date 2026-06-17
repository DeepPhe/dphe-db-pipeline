"""Stage 2 CSV-mode ingestion tests.

Covers the CSV -> SQLite table step behind ``--source-type csv``
(``config_processor.process_csv_file`` -> ``db.utils.csv_ops.process_a_csv_file``):
table creation from the CSV header, row insertion, and drop-and-recreate on
re-import.

The downstream config-driven OMOP transforms (change_column_types, lookup
tables, ICD translation, concept translation) are a separate integration
concern that needs SNOMED/ICD lookup fixtures and are not exercised here -- see
TODO.md.
"""

import sqlite3
from pathlib import Path

import pytest

from dphe_db_pipeline.omop_importer.source.config_processor import process_csv_file


def _ingest(db_path: Path, csv_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        process_csv_file(cur, conn, str(csv_path))
    finally:
        cur.close()
        conn.close()


def test_process_csv_file_creates_table_and_inserts_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # process_a_csv_file appends to ./process.log; run in tmp_path to contain it.
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "DEMOGRAPHIC_BRCAOVCA_VW.csv"
    csv_path.write_text(
        "PERSON_ID,GENDER_CONCEPT_ID,YEAR_OF_BIRTH\n1,8532,1960\n2,8507,1972\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "omop.sqlite3"

    _ingest(db_path, csv_path)

    conn = sqlite3.connect(str(db_path))
    try:
        # Table is named after the CSV file (minus extension); all columns TEXT.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(DEMOGRAPHIC_BRCAOVCA_VW)")]
        rows = conn.execute(
            "SELECT PERSON_ID, GENDER_CONCEPT_ID, YEAR_OF_BIRTH "
            "FROM DEMOGRAPHIC_BRCAOVCA_VW ORDER BY PERSON_ID"
        ).fetchall()
    finally:
        conn.close()

    assert cols == ["PERSON_ID", "GENDER_CONCEPT_ID", "YEAR_OF_BIRTH"]
    assert rows == [("1", "8532", "1960"), ("2", "8507", "1972")]


def test_process_csv_file_recreates_table_on_reimport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "SRC.csv"
    csv_path.write_text("A,B\n1,2\n", encoding="utf-8")
    db_path = tmp_path / "omop.sqlite3"

    _ingest(db_path, csv_path)
    _ingest(db_path, csv_path)

    conn = sqlite3.connect(str(db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM SRC").fetchone()[0]
    finally:
        conn.close()

    # Drop-and-recreate means a re-import replaces rather than duplicates rows.
    assert count == 1
