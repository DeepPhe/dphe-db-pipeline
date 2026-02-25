#!/usr/bin/env python3
"""
Test script to verify parse_concepts_by_group.py works correctly.

This script parses extracted_concepts.csv and shows a sample of the output.
"""

import csv
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import defaultdict


def parse_concepts_csv(csv_file: Path) -> Dict[Tuple[str, str, bool], Set[str]]:
    """Parse extracted_concepts.csv and group patients by concept."""
    concepts_by_group = defaultdict(set)

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            patient_id = row['patient_id']
            dphe_group = row['dpheGroup']
            class_uri = row['classUri']
            negated = row['negated'].lower() == 'true'

            concept_key = (dphe_group, class_uri, negated)
            concepts_by_group[concept_key].add(patient_id)

    return concepts_by_group


def main():
    """Test the parsing logic."""
    base_dir = Path(__file__).parent.parent
    concepts_file = base_dir / "extracted_cancer_data" / "extracted_concepts.csv"

    if not concepts_file.exists():
        print(f"Error: {concepts_file} not found!")
        return

    print(f"✓ Found: {concepts_file}")
    print(f"✓ File size: {concepts_file.stat().st_size} bytes")

    print("\nParsing concepts...")
    concepts_by_group = parse_concepts_csv(concepts_file)

    print(f"✓ Successfully parsed {len(concepts_by_group)} unique concepts\n")

    # Print sample
    print("="*120)
    print("SAMPLE OUTPUT (first 20 concepts)")
    print("="*120 + "\n")

    sorted_concepts = sorted(
        concepts_by_group.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2])
    )

    for i, ((dphe_group, class_uri, negated), patient_ids) in enumerate(sorted_concepts[:20], 1):
        negated_str = "NEGATED" if negated else "NOT_NEGATED"
        patient_list = ", ".join(sorted(patient_ids))
        num_patients = len(patient_ids)

        print(f"{i:2}. dpheGroup: {dphe_group:40} | classUri: {class_uri:40} | {negated_str:12} | Patients ({num_patients}): {patient_list}")

    print("\n" + "="*120)
    print("STATISTICS")
    print("="*120)

    all_patients = set()
    for patient_ids in concepts_by_group.values():
        all_patients.update(patient_ids)

    total_patients = len(all_patients)
    negated_count = sum(1 for (_, _, negated) in concepts_by_group.keys() if negated)
    not_negated_count = len(concepts_by_group) - negated_count

    print(f"Total unique concepts: {len(concepts_by_group)}")
    print(f"Total patients: {total_patients}")
    print(f"Negated concepts: {negated_count}")
    print(f"Not negated concepts: {not_negated_count}")

    # Top 10
    most_common = sorted(
        concepts_by_group.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    print("\n" + "="*120)
    print("TOP 10 MOST COMMON CONCEPTS (by number of patients)")
    print("="*120 + "\n")

    for i, ((dphe_group, class_uri, negated), patient_ids) in enumerate(most_common, 1):
        negated_str = "NEGATED" if negated else "NOT_NEGATED"
        print(f"{i:2}. {dphe_group:40} | {class_uri:40} | {negated_str:12} | {len(patient_ids):3} patients: {', '.join(sorted(patient_ids))}")

    print("\n✓ Parse test completed successfully!")


if __name__ == "__main__":
    main()
