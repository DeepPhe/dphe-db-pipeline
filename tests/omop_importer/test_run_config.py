import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from dphe_db_pipeline.omop_importer import run


@contextmanager
def temporary_cwd(path: str):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class RunConfigTests(unittest.TestCase):
    def test_load_tasks_config_supports_export_default_js(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "omop-config.js")
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write("export default {\n  \"before_update\": {},\n  \"after_update\": {}\n};\n")

            tasks_config = run.load_tasks_config(config_path)

        self.assertEqual(tasks_config, {"before_update": {}, "after_update": {}})

    def test_load_config_rejects_invalid_source_type(self) -> None:
        with patch.dict(os.environ, {"SOURCE_TYPE": "bogus", "SQLITE_DB_PATH": "test.sqlite3"}, clear=True):
            with self.assertRaises(ValueError):
                run.load_config()

    def test_load_config_json_requires_json_source_path(self) -> None:
        with patch.dict(
            os.environ,
            {"SOURCE_TYPE": "json", "SQLITE_DB_PATH": "test.sqlite3"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                run.load_config()

    def test_load_config_json_accepts_json_without_source_dir(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SOURCE_TYPE": "json",
                "SQLITE_DB_PATH": "test.sqlite3",
                "JSON_SOURCE_PATH": "patients.json",
            },
            clear=True,
        ):
            config = run.load_config()

        self.assertEqual(config["SOURCE_TYPE"], "json")
        self.assertEqual(config["JSON_SOURCE_PATH"], "patients.json")
        self.assertEqual(config.get("SOURCE_DIR"), "")

    def test_load_config_csv_allows_runtime_source_dir_override(self) -> None:
        with patch.dict(
            os.environ,
            {"SOURCE_TYPE": "csv", "SQLITE_DB_PATH": "test.sqlite3"},
            clear=True,
        ):
            config = run.load_config()

        self.assertEqual(config["SOURCE_TYPE"], "csv")
        self.assertEqual(config["SOURCE_DIR"], "")

    def test_load_config_mysql_requires_all_connection_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SOURCE_TYPE": "mysql",
                "SQLITE_DB_PATH": "test.sqlite3",
                "MYSQL_HOST": "127.0.0.1",
                "MYSQL_PORT": "3306",
                "MYSQL_USER": "user",
                "MYSQL_PASSWORD": "pw",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                run.load_config()

    def test_check_env_json_does_not_require_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = os.path.join(tmp_dir, ".env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "SOURCE_TYPE=json\n"
                    "SQLITE_DB_PATH=test.sqlite3\n"
                    "JSON_SOURCE_PATH=patients.json\n"
                )

            with temporary_cwd(tmp_dir):
                self.assertTrue(run.check_env())

    def test_check_env_csv_requires_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = os.path.join(tmp_dir, ".env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "SOURCE_TYPE=csv\n"
                    "SQLITE_DB_PATH=test.sqlite3\n"
                )

            with temporary_cwd(tmp_dir):
                self.assertFalse(run.check_env())

    def test_open_sqlite_sets_expected_pragmas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "pragma-test.sqlite3")
            conn = run._open_sqlite(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys")
            foreign_keys = cur.fetchone()[0]
            cur.execute("PRAGMA journal_mode")
            journal_mode = cur.fetchone()[0]
            cur.execute("PRAGMA busy_timeout")
            busy_timeout = cur.fetchone()[0]
            conn.close()

        self.assertEqual(foreign_keys, 1)
        self.assertEqual(str(journal_mode).lower(), "wal")
        self.assertEqual(busy_timeout, 30000)

    def test_run_csv_import_raises_when_worker_reports_failure(self) -> None:
        class FakePool:
            def __init__(self, processes: int) -> None:
                self.processes = processes

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def map(self, worker_func, csv_files):
                return [(csv_files[0], False, "Error processing bad.csv: boom")]

        with patch("dphe_db_pipeline.omop_importer.run.mp.Pool", FakePool):
            with self.assertRaisesRegex(RuntimeError, "CSV import failed"):
                run.run_csv_import(["bad.csv"], {"SQLITE_DB_PATH": "unused.sqlite3"})

    def test_main_json_mode_calls_json_import_and_skips_source_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = os.path.join(tmp_dir, "omop-config.js")
            db_path = os.path.join(tmp_dir, "main-test.sqlite3")
            json_path = os.path.join(tmp_dir, "patients.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write("export default {};\n")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump({"patients": []}, handle)

            conn_one = sqlite3.connect(db_path)
            conn_two = sqlite3.connect(db_path)

            with patch.object(sys, "argv", ["run.py", "--omop-config", config_path, "--source-type", "json"]), \
                patch("dphe_db_pipeline.omop_importer.run.load_config", return_value={
                    "SOURCE_TYPE": "json",
                    "SQLITE_DB_PATH": db_path,
                    "JSON_SOURCE_PATH": json_path,
                }), \
                patch("dphe_db_pipeline.omop_importer.run._open_sqlite", side_effect=[conn_one, conn_two]), \
                patch("dphe_db_pipeline.omop_importer.run.drop_table") as mock_drop_table, \
                patch("dphe_db_pipeline.omop_importer.run.run_json_import") as mock_run_json_import, \
                patch("dphe_db_pipeline.omop_importer.run.change_column_types") as mock_change_column_types, \
                patch("dphe_db_pipeline.omop_importer.run.add_indexes_before_update") as mock_add_indexes_before_update, \
                patch("dphe_db_pipeline.omop_importer.run.create_lookup_tables") as mock_create_lookup_tables, \
                patch("dphe_db_pipeline.omop_importer.run.create_columns") as mock_create_columns, \
                patch("dphe_db_pipeline.omop_importer.run.add_indexes_after_update") as mock_add_indexes_after_update, \
                patch("dphe_db_pipeline.omop_importer.run.process_translation") as mock_process_translation:
                run.main()

            self.assertEqual(mock_drop_table.call_count, 4)
            mock_run_json_import.assert_called_once()
            called_json_path = mock_run_json_import.call_args[0][0]
            self.assertEqual(called_json_path, json_path)
            mock_change_column_types.assert_not_called()
            mock_add_indexes_before_update.assert_not_called()
            mock_create_lookup_tables.assert_not_called()
            mock_create_columns.assert_not_called()
            mock_add_indexes_after_update.assert_not_called()
            mock_process_translation.assert_not_called()


if __name__ == "__main__":
    unittest.main()

