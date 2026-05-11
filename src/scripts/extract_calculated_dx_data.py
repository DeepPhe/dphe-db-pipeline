#!/usr/bin/env python3
"""
Script to extract patients grouped by cancer type from CALCULATED_DX_DATA table.

Queries the CALCULATED_DX_DATA table and returns all patients for each distinct CANCER value.
Exports summary bitmaps to extracted_cancer_data/omop.age_at_dx.csv and extracted_cancer_data/omop_cancers.csv.
"""

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_default_db_path() -> Path:
    """Return the default path to the DeepPhe OMOP SQLite database."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "deepphe" / "deepphe.sqlite3"


def get_patients_by_cancer(db_path: Path) -> Dict[str, List[Dict]]:
    """
    Query the CALCULATED_DX_DATA table and group patients by cancer type.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary mapping CANCER values to list of patient records
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all distinct cancer types
    cursor.execute("SELECT DISTINCT CANCER FROM CALCULATED_DX_DATA WHERE CANCER IS NOT NULL ORDER BY CANCER")
    cancer_types = [row[0] for row in cursor.fetchall()]

    # Get all records and group by cancer
    cursor.execute(
        "SELECT PERSON_ID, CODE, VOCAB, CANCER, DATE, AGE_AT_DX "
        "FROM CALCULATED_DX_DATA "
        "WHERE CANCER IS NOT NULL "
        "ORDER BY CANCER, PERSON_ID, DATE"
    )
    records = cursor.fetchall()

    # Group records by cancer type
    patients_by_cancer: Dict[str, List[Dict]] = {}
    for record in records:
        cancer = record['CANCER']
        if cancer not in patients_by_cancer:
            patients_by_cancer[cancer] = []

        patients_by_cancer[cancer].append({
            'PERSON_ID': record['PERSON_ID'],
            'CODE': record['CODE'],
            'VOCAB': record['VOCAB'],
            'DATE': record['DATE'],
            'AGE_AT_DX': record['AGE_AT_DX']
        })

    conn.close()

    return patients_by_cancer


def get_unique_patients_by_cancer(db_path: Path) -> Dict[str, List[str]]:
    """
    Get unique patients grouped by cancer type.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Dictionary mapping CANCER values to list of unique PERSON_IDs
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all distinct cancer types
    cursor.execute("SELECT DISTINCT CANCER FROM CALCULATED_DX_DATA WHERE CANCER IS NOT NULL ORDER BY CANCER")
    cancer_types = [row[0] for row in cursor.fetchall()]

    # Get unique patients for each cancer type
    patients_by_cancer: Dict[str, List[str]] = {}
    for cancer in cancer_types:
        cursor.execute(
            "SELECT DISTINCT PERSON_ID FROM CALCULATED_DX_DATA WHERE CANCER = ? ORDER BY PERSON_ID",
            (cancer,)
        )
        patients = [row[0] for row in cursor.fetchall()]
        patients_by_cancer[cancer] = patients

    conn.close()

    return patients_by_cancer


def group_patients_by_age(patients: List[Dict]) -> Dict[str, Set[str]]:
    """Group patients by their AGE_AT_DX value."""
    age_groups: defaultdict[str, Set[str]] = defaultdict(set)

    for patient in patients:
        raw_age = patient.get('AGE_AT_DX')
        age_value = "UNKNOWN" if raw_age is None else str(raw_age)
        age_groups[age_value].add(str(patient['PERSON_ID']))

    return dict(age_groups)


def aggregate_age_groups(patients_by_cancer: Dict[str, List[Dict]]) -> Dict[str, Set[str]]:
    """Aggregate age groups across all cancers."""
    all_patients = [patient for patient_list in patients_by_cancer.values() for patient in patient_list]
    return group_patients_by_age(all_patients)


def aggregate_cancer_groups(patients_by_cancer: Dict[str, List[Dict]]) -> Dict[str, Set[str]]:
    """Aggregate unique patients by CANCER value."""
    cancer_groups: Dict[str, Set[str]] = {}
    for cancer, patients in patients_by_cancer.items():
        if cancer is None:
            continue
        if cancer not in cancer_groups:
            cancer_groups[cancer] = set()
        for patient in patients:
            cancer_groups[cancer].add(str(patient['PERSON_ID']))
    return cancer_groups


def sort_age_groups(age_groups: Dict[str, Set[str]]):
    """Return age groups sorted numerically when possible, otherwise lexicographically."""
    def sort_key(item):
        age_value, _ = item
        try:
            return (0, float(age_value))
        except (TypeError, ValueError):
            return (1, age_value)

    return sorted(age_groups.items(), key=sort_key)


def sort_cancer_groups(cancer_groups: Dict[str, Set[str]]) -> List[Tuple[str, Set[str]]]:
    """Return cancer groups sorted lexicographically by cancer code/value."""
    return sorted(cancer_groups.items(), key=lambda item: item[0])


def export_age_groups_to_csv(age_groups: Dict[str, Set[str]], output_file: Path) -> None:
    """Export AGE_AT_DX groups to CSV with patient ID bitmap."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["age_at_dx", "num_patients", "patient_ids"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for age_value, patient_ids in sort_age_groups(age_groups):
            writer.writerow({
                "age_at_dx": age_value,
                "num_patients": len(patient_ids),
                "patient_ids": ", ".join(sorted(patient_ids)),
            })


def export_cancer_groups_to_csv(cancer_groups: Dict[str, Set[str]], output_file: Path) -> None:
    """Export CANCER groups to CSV with patient ID bitmap."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["cancer", "num_patients", "patient_ids"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for cancer_value, patient_ids in sort_cancer_groups(cancer_groups):
            writer.writerow({
                "cancer": cancer_value,
                "num_patients": len(patient_ids),
                "patient_ids": ", ".join(sorted(patient_ids)),
            })


def display_results(patients_by_cancer: Dict[str, List[Dict]]) -> None:
    """
    Display the extracted data in a readable format.

    Args:
        patients_by_cancer: Dictionary mapping CANCER values to patient records
    """
    print("="*80)
    print("CALCULATED_DX_DATA - PATIENTS GROUPED BY CANCER TYPE")
    print("="*80)

    total_cancers = len(patients_by_cancer)
    total_records = sum(len(patients) for patients in patients_by_cancer.values())

    print(f"\nTotal Cancer Types: {total_cancers}")
    print(f"Total Records: {total_records}")
    print("\n" + "="*80)

    for cancer, patients in patients_by_cancer.items():
        print(f"\nCANCER: {cancer}")
        print("-"*80)
        print(f"  Number of records: {len(patients)}")

        # Get unique patients
        unique_patients = list(set(p['PERSON_ID'] for p in patients))
        print(f"  Unique patients: {len(unique_patients)}")

        age_groups = group_patients_by_age(patients)
        print("\n  AGE_AT_DX -> Patients")
        for age_value, patient_ids in sort_age_groups(age_groups):
            patient_list = ", ".join(sorted(patient_ids))
            print(f"    Age {age_value:>6}: {len(patient_ids):3} patients | {patient_list}")

        print(f"\n  Patients:")
        for patient in patients[:10]:  # Show first 10 records
            print(f"    - PERSON_ID: {patient['PERSON_ID']}")
            print(f"      CODE: {patient['CODE']}")
            print(f"      VOCAB: {patient['VOCAB']}")
            print(f"      DATE: {patient['DATE']}")
            print(f"      AGE_AT_DX: {patient['AGE_AT_DX']}")

        if len(patients) > 10:
            print(f"    ... and {len(patients) - 10} more records")

    print("\n" + "="*80)


def main():
    """Main entry point."""
    import argparse

    default_db = get_default_db_path()
    parser = argparse.ArgumentParser(
        description="Extract patients grouped by cancer type from CALCULATED_DX_DATA."
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

    # Get patients by cancer
    patients_by_cancer = get_patients_by_cancer(db_path)

    # Display results
    display_results(patients_by_cancer)

    # Export AGE_AT_DX groups across all cancers
    age_groups = aggregate_age_groups(patients_by_cancer)
    base_dir = Path(__file__).resolve().parents[2] / "extracted_cancer_data"
    export_age_groups_to_csv(age_groups, base_dir / "omop.age_at_dx.csv")
    print(f"\nCSV written to: {base_dir / 'omop.age_at_dx.csv'}")

    # Export CANCER groups across all cancers
    cancer_groups = aggregate_cancer_groups(patients_by_cancer)
    export_cancer_groups_to_csv(cancer_groups, base_dir / "omop_cancers.csv")
    print(f"CSV written to: {base_dir / 'omop_cancers.csv'}")


if __name__ == "__main__":
    main()
