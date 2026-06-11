#!/usr/bin/env python3
"""
Parse extracted_attributes_*.csv files and list all patients for each unique
attribute.

Groups attributes by name, classUri, and modifiers (negated, uncertain,
historic), then lists all patients that have each unique attribute classUri.
"""

import csv
from collections import defaultdict
from pathlib import Path


def parse_attributes_csv_files(attributes_dir: Path) -> dict[tuple[str, str, bool, bool, bool], set[str]]:
    """
    Parse all extracted_attributes_*.csv files and group patients by attribute.

    Args:
        attributes_dir: Path to directory containing extracted_attributes_*.csv files

    Returns:
        Dictionary mapping
        (attribute_name, classUri, negated, uncertain, historic)
        to set of patient IDs
    """
    attributes_by_group = defaultdict(set)

    # Find all extracted_attributes_*.csv files
    attribute_files = sorted(attributes_dir.glob("extracted_attributes_*.csv"))

    if not attribute_files:
        raise FileNotFoundError(f"No extracted_attributes_*.csv files found in {attributes_dir}")

    print(f"Found {len(attribute_files)} attribute files to process")

    for csv_file in attribute_files:
        print(f"  Processing {csv_file.name}...")
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                patient_id = row['patient_id']
                attribute_name = row['attribute_name']
                class_uri = row['classUri']
                negated = row['negated'].lower() == 'true'
                uncertain = row['uncertain'].lower() == 'true'
                historic = row['historic'].lower() == 'true'

                # Group by normalized identity; ignore display text "value".
                attribute_key = (attribute_name, class_uri, negated, uncertain, historic)
                attributes_by_group[attribute_key].add(patient_id)

    return attributes_by_group


def print_attributes_by_group(attributes_by_group: dict[tuple[str, str, bool, bool, bool], set[str]]) -> None:
    """
    Print attributes grouped by name, classUri, and modifiers.

    Args:
        attributes_by_group: Dictionary mapping attribute keys to patient sets
    """
    # Sort by attribute_name, classUri, then modifiers
    sorted_attributes = sorted(
        attributes_by_group.items(),
        key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3], x[0][4])
    )

    print("\n" + "="*150)
    print("ATTRIBUTES GROUPED BY name, classUri, AND MODIFIERS")
    print("="*150 + "\n")

    for (attr_name, class_uri, negated, uncertain, historic), patient_ids in sorted_attributes:
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

        print(f"Name: {attr_name:30} | classUri: {class_uri:40} | {modifiers_str:30} | Patients ({num_patients}): {patient_list}")


def export_to_csv(attributes_by_group: dict[tuple[str, str, bool, bool, bool], set[str]], output_file: Path) -> None:
    """
    Export grouped attributes to CSV file.

    Args:
        attributes_by_group: Dictionary mapping attribute keys to patient sets
        output_file: Output CSV file path
    """
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['attribute_name', 'classUri', 'negated', 'uncertain', 'historic', 'num_patients', 'patient_ids']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by attribute_name, classUri, then modifiers
        sorted_attributes = sorted(
            attributes_by_group.items(),
            key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3], x[0][4])
        )

        for (attr_name, class_uri, negated, uncertain, historic), patient_ids in sorted_attributes:
            sorted_patients = ", ".join(sorted(patient_ids))
            writer.writerow({
                'attribute_name': attr_name,
                'classUri': class_uri,
                'negated': negated,
                'uncertain': uncertain,
                'historic': historic,
                'num_patients': len(patient_ids),
                'patient_ids': sorted_patients
            })


def print_statistics(attributes_by_group: dict[tuple[str, str, bool, bool, bool], set[str]]) -> None:
    """
    Print statistics about the attributes.

    Args:
        attributes_by_group: Dictionary mapping attribute keys to patient sets
    """
    total_attributes = len(attributes_by_group)
    all_patients = set()

    for patient_ids in attributes_by_group.values():
        all_patients.update(patient_ids)

    total_patients = len(all_patients)

    # Count by modifiers
    negated_count = sum(1 for (_, _, negated, _, _) in attributes_by_group.keys() if negated)
    uncertain_count = sum(1 for (_, _, _, uncertain, _) in attributes_by_group.keys() if uncertain)
    historic_count = sum(1 for (_, _, _, _, historic) in attributes_by_group.keys() if historic)

    # Find most common attributes
    most_common = sorted(
        attributes_by_group.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    print("\n" + "="*150)
    print("STATISTICS")
    print("="*150)
    print(f"Total unique attributes: {total_attributes}")
    print(f"Total patients: {total_patients}")
    print(f"Attributes with negated: {negated_count}")
    print(f"Attributes with uncertain: {uncertain_count}")
    print(f"Attributes with historic: {historic_count}")

    print("\n" + "="*150)
    print("TOP 10 MOST COMMON ATTRIBUTES (by number of patients)")
    print("="*150 + "\n")

    for i, ((attr_name, class_uri, negated, uncertain, historic), patient_ids) in enumerate(most_common, 1):
        modifiers = []
        if negated:
            modifiers.append("NEGATED")
        if uncertain:
            modifiers.append("UNCERTAIN")
        if historic:
            modifiers.append("HISTORIC")
        modifiers_str = "|".join(modifiers) if modifiers else "NONE"

        print(f"{i:2}. Name: {attr_name:30} | classUri: {class_uri:40} | {modifiers_str:30} | {len(patient_ids):3} patients")


def main():
    """Main entry point."""
    base_dir = Path(__file__).resolve().parents[4]
    attributes_dir = base_dir / "output" / "extraction" / "data" / "extracted_attributes"
    output_file = base_dir / "output" / "extraction" / "data" / "attributes_by_group.csv"

    if not attributes_dir.exists():
        print(f"Error: {attributes_dir} not found!")
        return

    print(f"Parsing attribute files from {attributes_dir}...\n")
    attributes_by_group = parse_attributes_csv_files(attributes_dir)

    # Print results
    print_attributes_by_group(attributes_by_group)

    # Print statistics
    print_statistics(attributes_by_group)

    # Export to CSV
    export_to_csv(attributes_by_group, output_file)
    print(f"\n✓ Results exported to: {output_file}")


if __name__ == "__main__":
    main()
