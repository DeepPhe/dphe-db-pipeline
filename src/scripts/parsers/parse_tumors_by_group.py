#!/usr/bin/env python3
"""
Parse extracted_tumors_*.csv files and list all patients for each unique tumor.

Groups tumors by classUri and modifiers (negated, uncertain, historic),
then lists all patients that have each unique tumor.
"""

import csv
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import defaultdict


def parse_tumors_csv_files(tumors_dir: Path) -> Dict[Tuple[str, bool, bool, bool], Set[str]]:
    """
    Parse all extracted_tumors_*.csv files and group patients by tumor.

    Args:
        tumors_dir: Path to directory containing extracted_tumors_*.csv files

    Returns:
        Dictionary mapping (classUri, negated, uncertain, historic) to set of patient IDs
    """
    tumors_by_group = defaultdict(set)

    # Find all extracted_tumors_*.csv files
    tumor_files = sorted(tumors_dir.glob("extracted_tumors_*.csv"))

    if not tumor_files:
        raise FileNotFoundError(f"No extracted_tumors_*.csv files found in {tumors_dir}")

    print(f"Found {len(tumor_files)} tumor files to process")

    for csv_file in tumor_files:
        print(f"  Processing {csv_file.name}...")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                patient_id = row['patient_id']
                class_uri = row['classUri']
                negated = row['negated'].lower() == 'true'
                uncertain = row['uncertain'].lower() == 'true'
                historic = row['historic'].lower() == 'true'

                # Create tumor key: (classUri, negated, uncertain, historic)
                tumor_key = (class_uri, negated, uncertain, historic)
                tumors_by_group[tumor_key].add(patient_id)

    return tumors_by_group


def print_tumors_by_group(tumors_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]]) -> None:
    """
    Print tumors grouped by classUri and modifiers.

    Args:
        tumors_by_group: Dictionary mapping tumor keys to patient sets
    """
    # Sort by classUri, then modifiers
    sorted_tumors = sorted(
        tumors_by_group.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])
    )

    print("\n" + "="*140)
    print("TUMORS GROUPED BY classUri AND MODIFIERS")
    print("="*140 + "\n")

    for (class_uri, negated, uncertain, historic), patient_ids in sorted_tumors:
        modifiers = []
        if negated:
            modifiers.append("NEGATED")
        if uncertain:
            modifiers.append("UNCERTAIN")
        if historic:
            modifiers.append("HISTORIC")
        modifiers_str = "|".join(modifiers) if modifiers else "NONE"

        patient_list = ", ".join(sorted(patient_ids))
        num_patients = len(patient_ids)

        print(f"classUri: {class_uri:50} | {modifiers_str:30} | Patients ({num_patients}): {patient_list}")


def export_to_csv(tumors_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]], output_file: Path) -> None:
    """
    Export grouped tumors to CSV file.

    Args:
        tumors_by_group: Dictionary mapping tumor keys to patient sets
        output_file: Output CSV file path
    """
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['classUri', 'negated', 'uncertain', 'historic', 'num_patients', 'patient_ids']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by classUri, then modifiers
        sorted_tumors = sorted(
            tumors_by_group.items(),
            key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])
        )

        for (class_uri, negated, uncertain, historic), patient_ids in sorted_tumors:
            sorted_patients = ", ".join(sorted(patient_ids))
            writer.writerow({
                'classUri': class_uri,
                'negated': negated,
                'uncertain': uncertain,
                'historic': historic,
                'num_patients': len(patient_ids),
                'patient_ids': sorted_patients
            })


def print_statistics(tumors_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]]) -> None:
    """
    Print statistics about the tumors.

    Args:
        tumors_by_group: Dictionary mapping tumor keys to patient sets
    """
    total_tumors = len(tumors_by_group)
    all_patients = set()

    for patient_ids in tumors_by_group.values():
        all_patients.update(patient_ids)

    total_patients = len(all_patients)

    # Count by modifiers
    negated_count = sum(1 for (_, negated, _, _) in tumors_by_group.keys() if negated)
    uncertain_count = sum(1 for (_, _, uncertain, _) in tumors_by_group.keys() if uncertain)
    historic_count = sum(1 for (_, _, _, historic) in tumors_by_group.keys() if historic)

    # Find most common tumors
    most_common = sorted(
        tumors_by_group.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    print("\n" + "="*140)
    print("STATISTICS")
    print("="*140)
    print(f"Total unique tumors: {total_tumors}")
    print(f"Total patients: {total_patients}")
    print(f"Tumors with negated: {negated_count}")
    print(f"Tumors with uncertain: {uncertain_count}")
    print(f"Tumors with historic: {historic_count}")

    print("\n" + "="*140)
    print("TOP 10 MOST COMMON TUMORS (by number of patients)")
    print("="*140 + "\n")

    for i, ((class_uri, negated, uncertain, historic), patient_ids) in enumerate(most_common, 1):
        modifiers = []
        if negated:
            modifiers.append("NEGATED")
        if uncertain:
            modifiers.append("UNCERTAIN")
        if historic:
            modifiers.append("HISTORIC")
        modifiers_str = "|".join(modifiers) if modifiers else "NONE"

        print(f"{i:2}. classUri: {class_uri:50} | {modifiers_str:30} | {len(patient_ids):3} patients: {', '.join(sorted(patient_ids)[:10])}")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent.parent
    tumors_dir = base_dir / "extracted_cancer_data" / "extracted_tumors"
    output_file = base_dir / "extracted_cancer_data" / "tumors_by_group.csv"

    if not tumors_dir.exists():
        print(f"Error: {tumors_dir} not found!")
        return

    print(f"Parsing tumor files from {tumors_dir}...\n")
    tumors_by_group = parse_tumors_csv_files(tumors_dir)

    # Print results
    print_tumors_by_group(tumors_by_group)

    # Print statistics
    print_statistics(tumors_by_group)

    # Export to CSV
    export_to_csv(tumors_by_group, output_file)
    print(f"\n✓ Results exported to: {output_file}")


if __name__ == "__main__":
    main()
