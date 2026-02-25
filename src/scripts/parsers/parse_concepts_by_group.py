#!/usr/bin/env python3
"""
Parse extracted_concepts_*.csv files and list all patients for each unique concept.

Groups concepts by dpheGroup, classUri, and negated status,
then lists all patients that have each unique concept.
"""

import csv
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import defaultdict

def parse_concepts_csv_files(concepts_dir: Path) -> Dict[Tuple[str, str, bool], Set[str]]:
    """
    Parse all extracted_concepts_*.csv files and group patients by concept.

    Args:
        concepts_dir: Path to directory containing extracted_concepts_*.csv files

    Returns:
        Dictionary mapping (dpheGroup, classUri, negated) to set of patient IDs
    """
    concepts_by_group = defaultdict(set)

    # Find all extracted_concepts_*.csv files
    concept_files = sorted(concepts_dir.glob("extracted_concepts_*.csv"))

    if not concept_files:
        raise FileNotFoundError(f"No extracted_concepts_*.csv files found in {concepts_dir}")

    print(f"Found {len(concept_files)} concept files to process")

    for csv_file in concept_files:
        print(f"  Processing {csv_file.name}...")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                patient_id = row['patient_id']
                dphe_group = row['dpheGroup']
                class_uri = row['classUri']
                negated = row['negated'].lower() == 'true'

                # Create concept key: (dpheGroup, classUri, negated)
                concept_key = (dphe_group, class_uri, negated)
                concepts_by_group[concept_key].add(patient_id)

    return concepts_by_group


def print_concepts_by_group(concepts_by_group: Dict[Tuple[str, str, bool], Set[str]]) -> None:
    """
    Print concepts grouped by dpheGroup, classUri, and negated status.

    Args:
        concepts_by_group: Dictionary mapping concept keys to patient sets
    """
    # Sort by dpheGroup, then classUri, then negated
    sorted_concepts = sorted(
        concepts_by_group.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2])
    )

    print("\n" + "="*120)
    print("CONCEPTS GROUPED BY dpheGroup, classUri, AND negated STATUS")
    print("="*120 + "\n")

    for (dphe_group, class_uri, negated), patient_ids in sorted_concepts:
        negated_str = "NEGATED" if negated else "NOT_NEGATED"
        patient_list = ", ".join(sorted(patient_ids))
        num_patients = len(patient_ids)

        print(f"dpheGroup: {dphe_group:40} | classUri: {class_uri:40} | {negated_str:12} | Patients ({num_patients}): {patient_list}")


def export_to_csv(concepts_by_group: Dict[Tuple[str, str, bool], Set[str]], output_file: Path) -> None:
    """
    Export grouped concepts to CSV file.

    Args:
        concepts_by_group: Dictionary mapping concept keys to patient sets
        output_file: Output CSV file path
    """
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['dpheGroup', 'classUri', 'negated', 'num_patients', 'patient_ids']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by dpheGroup, then classUri, then negated
        sorted_concepts = sorted(
            concepts_by_group.items(),
            key=lambda x: (x[0][0], x[0][1], x[0][2])
        )

        for (dphe_group, class_uri, negated), patient_ids in sorted_concepts:
            sorted_patients = ", ".join(sorted(patient_ids))
            writer.writerow({
                'dpheGroup': dphe_group,
                'classUri': class_uri,
                'negated': negated,
                'num_patients': len(patient_ids),
                'patient_ids': sorted_patients
            })


def print_statistics(concepts_by_group: Dict[Tuple[str, str, bool], Set[str]]) -> None:
    """
    Print statistics about the concepts.

    Args:
        concepts_by_group: Dictionary mapping concept keys to patient sets
    """
    total_concepts = len(concepts_by_group)
    all_patients = set()

    for patient_ids in concepts_by_group.values():
        all_patients.update(patient_ids)

    total_patients = len(all_patients)

    # Count negated vs not negated
    negated_count = sum(1 for (_, _, negated) in concepts_by_group.keys() if negated)
    not_negated_count = total_concepts - negated_count

    # Find most common concepts
    most_common = sorted(
        concepts_by_group.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    print("\n" + "="*120)
    print("STATISTICS")
    print("="*120)
    print(f"Total unique concepts: {total_concepts}")
    print(f"Total patients: {total_patients}")
    print(f"Negated concepts: {negated_count}")
    print(f"Not negated concepts: {not_negated_count}")

    print("\n" + "="*120)
    print("TOP 10 MOST COMMON CONCEPTS (by number of patients)")
    print("="*120 + "\n")

    for i, ((dphe_group, class_uri, negated), patient_ids) in enumerate(most_common, 1):
        negated_str = "NEGATED" if negated else "NOT_NEGATED"
        print(f"{i:2}. {dphe_group:40} | {class_uri:40} | {negated_str:12} | {len(patient_ids):3} patients: {', '.join(sorted(patient_ids))}")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent.parent
    concepts_dir = base_dir / "extracted_cancer_data" / "extracted_concepts"
    output_file = base_dir / "extracted_cancer_data" / "concepts_by_group.csv"

    if not concepts_dir.exists():
        print(f"Error: {concepts_dir} not found!")
        return

    print(f"Parsing concept files from {concepts_dir}...\n")
    concepts_by_group = parse_concepts_csv_files(concepts_dir)

    # Print results
    print_concepts_by_group(concepts_by_group)

    # Print statistics
    print_statistics(concepts_by_group)

    # Export to CSV
    export_to_csv(concepts_by_group, output_file)
    print(f"\n✓ Results exported to: {output_file}")


if __name__ == "__main__":
    main()
