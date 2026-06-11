#!/usr/bin/env python3
"""Regression tests for ignoring attribute `value` across the pipeline."""

import csv
import importlib.util
from pathlib import Path


def _load_module(relative_path: str, module_name: str):
    """Load a Python module from a repository-relative path."""
    repo_root = Path(__file__).resolve().parent.parent
    module_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_attributes_ignores_value_column(tmp_path):
    """Rows differing only by `value` should collapse into one grouped attribute."""
    parser_module = _load_module(
        "src/dphe_db_pipeline/extractor/parsers/parse_attributes_by_group.py",
        "parse_attributes_by_group_for_test",
    )

    input_csv = tmp_path / "extracted_attributes_1.csv"
    with open(input_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "patient_id",
                "attribute_name",
                "value",
                "classUri",
                "negated",
                "uncertain",
                "historic",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "patient_id": "p1",
                "attribute_name": "Course",
                "value": "",
                "classUri": "BulkyDisease",
                "negated": "False",
                "uncertain": "False",
                "historic": "False",
            }
        )
        writer.writerow(
            {
                "patient_id": "p2",
                "attribute_name": "Course",
                "value": "Bulky Disease",
                "classUri": "BulkyDisease",
                "negated": "False",
                "uncertain": "False",
                "historic": "False",
            }
        )

    grouped = parser_module.parse_attributes_csv_files(tmp_path)

    assert len(grouped) == 1
    only_group_patients = next(iter(grouped.values()))
    assert only_group_patients == {"p1", "p2"}

    grouped_csv = tmp_path / "attributes_by_group.csv"
    parser_module.export_to_csv(grouped, grouped_csv)
    with open(grouped_csv, encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert "value" not in reader.fieldnames


def test_extractor_does_not_emit_value_column(tmp_path):
    """CancerDataExtractor attribute output should never include a `value` field."""
    extractor_module = _load_module(
        "src/dphe_db_pipeline/extractor/extractors/extract_cancers_data.py",
        "extract_cancers_data_for_test",
    )

    extractor = extractor_module.CancerDataExtractor(tmp_path, patients_per_file=1)
    extractor.patient_order = ["p1"]
    extractor.patient_set = {"p1"}

    extractor._extract_attribute(
        attr={
            "name": "Course",
            "id": "attr-1",
            "values": [
                {
                    "value": "Bulky Disease",
                    "classUri": "BulkyDisease",
                    "id": "value-1",
                    "negated": False,
                    "uncertain": False,
                    "historic": False,
                    "confidence": 42,
                }
            ],
        },
        patient_id="p1",
        cancer_idx=0,
        tumor_idx=0,
        level="tumor",
        attr_idx=0,
    )

    assert len(extractor.attributes_data) == 1
    assert "value" not in extractor.attributes_data[0]

    extractor._write_csv_files()

    output_csv = tmp_path / "extracted_attributes" / "extracted_attributes_1.csv"
    assert output_csv.exists()

    with open(output_csv, encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert "value" not in reader.fieldnames


def test_importer_attributes_table_has_no_value_column(tmp_path):
    """Importer should create attributes_by_group table without a `value` column."""
    importer_module = _load_module(
        "src/dphe_db_pipeline/extractor/import_parsed_data.py",
        "import_parsed_data_for_test",
    )

    db_path = tmp_path / "test.sqlite"
    csv_path = tmp_path / "attributes_by_group.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "attribute_name",
                "classUri",
                "negated",
                "uncertain",
                "historic",
                "num_patients",
                "patient_ids",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "attribute_name": "Course",
                "classUri": "BulkyDisease",
                "negated": "False",
                "uncertain": "False",
                "historic": "True",
                "num_patients": "1",
                "patient_ids": "9999999999",
            }
        )

    importer = importer_module.DatabaseImporter(str(db_path))
    assert importer.connect() is True
    try:
        assert importer.create_and_import_attributes(csv_path) is True

        cursor = importer.conn.cursor()
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(attributes_by_group)")]
        assert "value" not in columns

        rows = cursor.execute(
            "SELECT attribute_name, classUri, num_patients FROM attributes_by_group"
        ).fetchall()
        assert rows == [("Course", "BulkyDisease", 1)]
    finally:
        importer.disconnect()
