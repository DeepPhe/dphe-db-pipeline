#!/usr/bin/env python3
"""
Extract patient demographics (gender, race, ethnicity) from CALCULATED_PATIENT_DATA
and emit bitmap CSV summaries under output/extraction/data/.

Outputs:
- output/extraction/data/omop_gender.csv
- output/extraction/data/omop_race.csv
- output/extraction/data/omop_ethnicity.csv
"""

import csv
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path


def get_default_db_path() -> Path:
    """Return the default absolute path to the DeepPhe OMOP SQLite database."""
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "output" / "databases" / "individual" / "omop.sqlite3"


def fetch_patient_records(db_path: Path) -> list[dict]:
    """Fetch patient records from CALCULATED_PATIENT_DATA."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT PERSON_ID, GENDER, RACE, ETHNICITY "
        "FROM CALCULATED_PATIENT_DATA "
        "WHERE PERSON_ID IS NOT NULL "
        "ORDER BY PERSON_ID"
    )
    records = cursor.fetchall()
    conn.close()
    return [dict(row) for row in records]


def group_patients_by_field(
    patients: Iterable[dict], field_name: str, unknown_label: str = "UNKNOWN"
) -> dict[str, set[str]]:
    """Group patient PERSON_IDs by a specific field value."""
    groups: defaultdict[str, set[str]] = defaultdict(set)
    for patient in patients:
        value = patient.get(field_name)
        group_key = unknown_label if value in (None, "") else str(value)
        groups[group_key].add(str(patient["PERSON_ID"]))
    return dict(groups)


def sort_group_items(groups: dict[str, set[str]]) -> list[tuple[str, set[str]]]:
    """Sort groups numerically when possible, otherwise lexicographically."""
    def sort_key(item: tuple[str, set[str]]):
        key, _ = item
        try:
            return (0, float(key))
        except (TypeError, ValueError):
            return (1, key)

    return sorted(groups.items(), key=sort_key)


def export_groups_to_csv(groups: dict[str, set[str]], output_file: Path, field_label: str) -> None:
    """Export grouped patient IDs to a CSV with bitmap-style patient lists."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [field_label, "num_patients", "patient_ids"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for value, patient_ids in sort_group_items(groups):
            writer.writerow({
                field_label: value,
                "num_patients": len(patient_ids),
                "patient_ids": ", ".join(sorted(patient_ids)),
            })


def display_summary(groups: dict[str, set[str]], title: str) -> None:
    """Print a brief summary of grouped patient counts."""
    print(f"\n{title}")
    print("-" * len(title))
    for value, patient_ids in sort_group_items(groups):
        print(f"  {value}: {len(patient_ids)} patients")


def main() -> None:
    """Entry point for extracting CALCULATED_PATIENT_DATA demographics."""
    import argparse

    default_db = get_default_db_path()
    parser = argparse.ArgumentParser(
        description="Extract patient demographics from CALCULATED_PATIENT_DATA."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=default_db,
        help=f"Path to the DeepPhe OMOP SQLite database (default: {default_db}).",
    )
    args = parser.parse_args()

    db_path: Path = args.database.resolve()
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        raise SystemExit(1)

    print(f"Connecting to database: {db_path}")
    patients = fetch_patient_records(db_path)
    if not patients:
        print("No patient records found in CALCULATED_PATIENT_DATA.")
        return

    base_dir = Path(__file__).resolve().parents[3] / "output" / "extraction" / "data"

    gender_groups = group_patients_by_field(patients, "GENDER")
    race_groups = group_patients_by_field(patients, "RACE")
    ethnicity_groups = group_patients_by_field(patients, "ETHNICITY")

    display_summary(gender_groups, "GENDER groups")
    display_summary(race_groups, "RACE groups")
    display_summary(ethnicity_groups, "ETHNICITY groups")

    export_groups_to_csv(gender_groups, base_dir / "omop_gender.csv", "gender")
    export_groups_to_csv(race_groups, base_dir / "omop_race.csv", "race")
    export_groups_to_csv(ethnicity_groups, base_dir / "omop_ethnicity.csv", "ethnicity")

    print("\nCSV outputs:")
    print(f"  {base_dir / 'omop_gender.csv'}")
    print(f"  {base_dir / 'omop_race.csv'}")
    print(f"  {base_dir / 'omop_ethnicity.csv'}")


if __name__ == "__main__":
    main()

