import json
import os
import sqlite3
import tempfile
import unittest

from dphe_db_pipeline.omop_importer.source.json_demographics_processor import run_json_import


class JsonDemographicsProcessorTests(unittest.TestCase):
    def run_import(self, payload_or_path):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, "test.sqlite3")
        conn = sqlite3.connect(db_path)
        self.addCleanup(conn.close)
        cur = conn.cursor()

        if isinstance(payload_or_path, str):
            json_path = payload_or_path
        else:
            json_path = os.path.join(temp_dir.name, "patients.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(payload_or_path, handle)

        run_json_import(json_path, conn, cur)
        return conn, cur, temp_dir.name

    def test_json_import_normalizes_and_upserts(self) -> None:
        payload = {
            "patients": [
                {
                    "PatientID": "p1",
                    "Gender": "female",
                    "Race": "white",
                    "DateOfBirth": "04-01-1960",
                    "CancerType": "BreastCancer",
                    "AgeAtDiagnosis": 50,
                },
                {
                    "PatientID": "p2",
                    "Gender": "male",
                    "Race": "black",
                    "DateOfBirth": "unknown",
                    "CancerType": "Melanoma",
                    "AgeAtDiagnosis": "61",
                },
                {
                    "PatientID": "p1",
                    "Gender": "female",
                    "Race": "white",
                    "DateOfBirth": "04-01-1960",
                    "CancerType": "OvarianCancer",
                    "AgeAtDiagnosis": 51,
                },
            ]
        }

        _, cur, _ = self.run_import(payload)

        cur.execute(
            "SELECT PERSON_ID, GENDER, RACE, DATE_OF_BIRTH FROM CALCULATED_PATIENT_DATA ORDER BY PERSON_ID"
        )
        self.assertEqual(
            cur.fetchall(),
            [
                ("p1", "female", "white", "1960-04-01"),
                ("p2", "male", "black", None),
            ],
        )

        cur.execute(
            "SELECT PERSON_ID, CANCER, AGE_AT_DX FROM CALCULATED_DX_DATA ORDER BY PERSON_ID"
        )
        self.assertEqual(cur.fetchall(), [("p1", "O", 51), ("p2", "M", 61)])

    def test_directory_ingestion_reads_multiple_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload_a = {"patients": [{"PatientID": "p1", "Gender": "female", "CancerType": "B"}]}
            payload_b = {"patients": [{"PatientID": "p2", "Gender": "male", "CancerType": "Melanoma"}]}
            with open(os.path.join(tmp_dir, "a.json"), "w", encoding="utf-8") as handle:
                json.dump(payload_a, handle)
            with open(os.path.join(tmp_dir, "b.json"), "w", encoding="utf-8") as handle:
                json.dump(payload_b, handle)
            with open(os.path.join(tmp_dir, "ignore.txt"), "w", encoding="utf-8") as handle:
                handle.write("ignore me")

            conn, cur, _ = self.run_import(tmp_dir)

            cur.execute("SELECT PERSON_ID, CANCER FROM CALCULATED_DX_DATA ORDER BY PERSON_ID")
            self.assertEqual(cur.fetchall(), [("p1", "B"), ("p2", "M")])

    def test_invalid_and_unknown_values_become_null_and_missing_ids_are_skipped(self) -> None:
        payload = {
            "patients": [
                {
                    "PatientID": "p1",
                    "DateOfBirth": "not-a-date",
                    "CancerType": "UnknownCancer",
                    "AgeAtDiagnosis": -1,
                    "Ethnicity": "Hispanic",
                },
                {
                    "PatientID": "p2",
                    "DateOfBirth": "1965-12-31",
                    "AgeAtDiagnosis": "n/a",
                    "CancerType": "  melanoma  ",
                },
                {
                    "Gender": "female"
                },
                "not-a-dict",
            ]
        }

        _, cur, _ = self.run_import(payload)

        cur.execute(
            "SELECT PERSON_ID, ETHNICITY, DATE_OF_BIRTH FROM CALCULATED_PATIENT_DATA ORDER BY PERSON_ID"
        )
        self.assertEqual(
            cur.fetchall(),
            [
                ("p1", "Hispanic", None),
                ("p2", None, "1965-12-31"),
            ],
        )

        cur.execute(
            "SELECT PERSON_ID, CANCER, AGE_AT_DX FROM CALCULATED_DX_DATA ORDER BY PERSON_ID"
        )
        self.assertEqual(cur.fetchall(), [("p1", None, None), ("p2", "M", None)])

    def test_missing_json_source_path_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.sqlite3")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            with self.assertRaises(FileNotFoundError):
                run_json_import(os.path.join(tmp_dir, "missing.json"), conn, cur)
            conn.close()

    def test_invalid_patients_shape_raises(self) -> None:
        payload = {"patients": {"PatientID": "p1"}}
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test.sqlite3")
            json_path = os.path.join(tmp_dir, "patients.json")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            with self.assertRaises(ValueError):
                run_json_import(json_path, conn, cur)
            conn.close()


if __name__ == "__main__":
    unittest.main()

