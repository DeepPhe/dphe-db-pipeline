#!/usr/bin/env python3
"""
Parse extracted_cancers_*.csv files and list all patients for each unique cancer.

Groups cancers by classUri and modifiers (negated, uncertain, historic),
then lists all patients that have each unique cancer.
"""

import csv
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import defaultdict


def parse_cancers_csv_files(cancers_dir: Path) -> Dict[Tuple[str, bool, bool, bool], Set[str]]:
    """
    Parse all extracted_cancers_*.csv files and group patients by cancer.

    Args:
        cancers_dir: Path to directory containing extracted_cancers_*.csv files

    Returns:
        Dictionary mapping (classUri, negated, uncertain, historic) to set of patient IDs
    """
    cancers_by_group = defaultdict(set)

    # Find all extracted_cancers_*.csv files
    cancer_files = sorted(cancers_dir.glob("extracted_cancers_*.csv"))

    if not cancer_files:
        raise FileNotFoundError(f"No extracted_cancers_*.csv files found in {cancers_dir}")

    print(f"Found {len(cancer_files)} cancer files to process")

    for csv_file in cancer_files:
        print(f"  Processing {csv_file.name}...")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                patient_id = row['patient_id']
                class_uri = row['classUri']
                negated = row['negated'].lower() == 'true'
                uncertain = row['uncertain'].lower() == 'true'
                historic = row['historic'].lower() == 'true'

                # Create cancer key: (classUri, negated, uncertain, historic)
                cancer_key = (class_uri, negated, uncertain, historic)
                cancers_by_group[cancer_key].add(patient_id)

    return cancers_by_group


def print_cancers_by_group(cancers_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]]) -> None:
    """
    Print cancers grouped by classUri and modifiers.

    Args:
        cancers_by_group: Dictionary mapping cancer keys to patient sets
    """
    # Sort by classUri, then modifiers
    sorted_cancers = sorted(
        cancers_by_group.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])
    )

    print("\n" + "="*140)
    print("CANCERS GROUPED BY classUri AND MODIFIERS")
    print("="*140 + "\n")

    for (class_uri, negated, uncertain, historic), patient_ids in sorted_cancers:
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


def export_to_csv(cancers_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]], output_file: Path) -> None:
    """
    Export grouped cancers to CSV file.

    Args:
        cancers_by_group: Dictionary mapping cancer keys to patient sets
        output_file: Output CSV file path
    """
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['classUri', 'negated', 'uncertain', 'historic', 'num_patients', 'patient_ids']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by classUri, then modifiers
        sorted_cancers = sorted(
            cancers_by_group.items(),
            key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])
        )

        for (class_uri, negated, uncertain, historic), patient_ids in sorted_cancers:
            sorted_patients = ", ".join(sorted(patient_ids))
            writer.writerow({
                'classUri': class_uri,
                'negated': negated,
                'uncertain': uncertain,
                'historic': historic,
                'num_patients': len(patient_ids),
                'patient_ids': sorted_patients
            })


def print_statistics(cancers_by_group: Dict[Tuple[str, bool, bool, bool], Set[str]]) -> None:
    """
    Print statistics about the cancers.

    Args:
        cancers_by_group: Dictionary mapping cancer keys to patient sets
    """
    total_cancers = len(cancers_by_group)
    all_patients = set()

    for patient_ids in cancers_by_group.values():
        all_patients.update(patient_ids)

    total_patients = len(all_patients)

    # Count by modifiers
    negated_count = sum(1 for (_, negated, _, _) in cancers_by_group.keys() if negated)
    uncertain_count = sum(1 for (_, _, uncertain, _) in cancers_by_group.keys() if uncertain)
    historic_count = sum(1 for (_, _, _, historic) in cancers_by_group.keys() if historic)

    # Find most common cancers
    most_common = sorted(
        cancers_by_group.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    print("\n" + "="*140)
    print("STATISTICS")
    print("="*140)
    print(f"Total unique cancers: {total_cancers}")
    print(f"Total patients: {total_patients}")
    print(f"Cancers with negated: {negated_count}")
    print(f"Cancers with uncertain: {uncertain_count}")
    print(f"Cancers with historic: {historic_count}")

    print("\n" + "="*140)
    print("TOP 10 MOST COMMON CANCERS (by number of patients)")
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
    base_dir = Path(__file__).parent
    cancers_dir = base_dir / "extracted_cancer_data" / "extracted_cancers"
    output_file = base_dir / "extracted_cancer_data" / "cancers_by_group.csv"

    if not cancers_dir.exists():
        print(f"Error: {cancers_dir} not found!")
        return

    print(f"Parsing cancer files from {cancers_dir}...\n")
    cancers_by_group = parse_cancers_csv_files(cancers_dir)

    # Print results
    print_cancers_by_group(cancers_by_group)

    # Print statistics
    print_statistics(cancers_by_group)

    # Export to CSV
    export_to_csv(cancers_by_group, output_file)
    print(f"\n✓ Results exported to: {output_file}")


if __name__ == "__main__":
    main()
