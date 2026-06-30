import sqlite3
from pathlib import Path

from dphe_db_pipeline.omop_importer import run
from dphe_db_pipeline.omop_importer.db.omop.lookup_table_ops import create_lookup_tables


def test_default_icd_lookup_loads_only_runtime_fields() -> None:
    importer_dir = (
        Path(__file__).resolve().parents[2] / "src" / "dphe_db_pipeline" / "omop_importer"
    )
    tasks_config = run.load_tasks_config(importer_dir / "omop-config.js")
    lookup_config = tasks_config["before_update"]["add_lookup_tables"]
    lookup_config["lookup_tables_dir"] = str(importer_dir / "lookup_tables")

    conn = sqlite3.connect(":memory:")
    try:
        create_lookup_tables({"lookup": conn.cursor()}, {"lookup": conn}, lookup_config)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(ICD_CODES)")]
        row_count = conn.execute("SELECT COUNT(*) FROM ICD_CODES").fetchone()[0]
    finally:
        conn.close()

    assert columns == ["CODE", "VOCAB", "CANCER"]
    assert row_count == 52
