import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from dphe_db_pipeline.extractor.generate_patient_summaries import main as summaries_main
from dphe_db_pipeline.extractor.import_parsed_data import DatabaseImporter


def test_drop_all_tables_removes_omop_bitmap_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "deepphe.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        for table_name in (
            "omop_age_at_dx",
            "omop_gender",
            "omop_race",
            "omop_ethnicity",
            "omop_cancers",
        ):
            conn.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    importer = DatabaseImporter(str(db_path))
    assert importer.connect()
    try:
        assert importer.drop_all_tables()
    finally:
        importer.disconnect()

    conn = sqlite3.connect(db_path)
    try:
        remaining_tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()

    assert not {
        "omop_age_at_dx",
        "omop_gender",
        "omop_race",
        "omop_ethnicity",
        "omop_cancers",
    }.intersection(remaining_tables)


def test_generate_patient_summaries_cli_fails_when_no_rows_written(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite3"
    db_path.touch()
    output_path = tmp_path / "patient_summaries.jsonl"

    with patch.object(
        sys,
        "argv",
        [
            "generate_patient_summaries.py",
            "--database",
            str(db_path),
            "--output",
            str(output_path),
        ],
    ):
        assert summaries_main() == 1
