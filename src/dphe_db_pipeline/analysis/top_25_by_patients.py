#!/usr/bin/env python3
"""
List top 25 items from each _by_group table ranked by number of patients.

Analyzes the four aggregated tables:
- attributes_by_group
- cancers_by_group
- concepts_by_group
- tumors_by_group

Shows the most common attributes, cancers, concepts, and tumors across all patients.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any


def get_top_attributes(conn: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    """
    Get top attributes by patient count.

    Args:
        conn: SQLite database connection
        limit: Number of results to return

    Returns:
        List of dictionaries with attribute information
    """
    cursor = conn.cursor()
    query = """
        SELECT
            attribute_name,
            value,
            classUri,
            negated,
            uncertain,
            historic,
            num_patients
        FROM attributes_by_group
        ORDER BY num_patients DESC, attribute_name ASC
        LIMIT ?
    """

    rows = cursor.execute(query, (limit,)).fetchall()

    return [
        {
            'attribute_name': row[0],
            'value': row[1],
            'classUri': row[2],
            'negated': bool(row[3]),
            'uncertain': bool(row[4]),
            'historic': bool(row[5]),
            'num_patients': row[6]
        }
        for row in rows
    ]


def get_top_cancers(conn: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    """
    Get top cancers by patient count.

    Args:
        conn: SQLite database connection
        limit: Number of results to return

    Returns:
        List of dictionaries with cancer information
    """
    cursor = conn.cursor()
    query = """
        SELECT
            classUri,
            negated,
            uncertain,
            historic,
            num_patients
        FROM cancers_by_group
        ORDER BY num_patients DESC, classUri ASC
        LIMIT ?
    """

    rows = cursor.execute(query, (limit,)).fetchall()

    return [
        {
            'classUri': row[0],
            'negated': bool(row[1]),
            'uncertain': bool(row[2]),
            'historic': bool(row[3]),
            'num_patients': row[4]
        }
        for row in rows
    ]


def get_top_concepts(conn: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    """
    Get top concepts by patient count.

    Args:
        conn: SQLite database connection
        limit: Number of results to return

    Returns:
        List of dictionaries with concept information
    """
    cursor = conn.cursor()
    query = """
        SELECT
            dpheGroup,
            classUri,
            negated,
            num_patients
        FROM concepts_by_group
        ORDER BY num_patients DESC, dpheGroup ASC
        LIMIT ?
    """

    rows = cursor.execute(query, (limit,)).fetchall()

    return [
        {
            'dpheGroup': row[0],
            'classUri': row[1],
            'negated': bool(row[2]),
            'num_patients': row[3]
        }
        for row in rows
    ]


def get_top_tumors(conn: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    """
    Get top tumors by patient count.

    Args:
        conn: SQLite database connection
        limit: Number of results to return

    Returns:
        List of dictionaries with tumor information
    """
    cursor = conn.cursor()
    query = """
        SELECT
            classUri,
            negated,
            uncertain,
            historic,
            num_patients
        FROM tumors_by_group
        ORDER BY num_patients DESC, classUri ASC
        LIMIT ?
    """

    rows = cursor.execute(query, (limit,)).fetchall()

    return [
        {
            'classUri': row[0],
            'negated': bool(row[1]),
            'uncertain': bool(row[2]),
            'historic': bool(row[3]),
            'num_patients': row[4]
        }
        for row in rows
    ]


def format_modifiers(
    negated: bool,
    uncertain: bool | None = None,
    historic: bool | None = None,
) -> str:
    """
    Format modifier flags into a readable string.

    Args:
        negated: Negated flag
        uncertain: Uncertain flag (optional)
        historic: Historic flag (optional)

    Returns:
        Formatted modifier string
    """
    modifiers = []
    if negated:
        modifiers.append("NEG")
    if uncertain:
        modifiers.append("UNC")
    if historic:
        modifiers.append("HIST")

    return "|".join(modifiers) if modifiers else "-"


def extract_class_name(class_uri: str) -> str:
    """
    Extract the class name from a URI.

    Args:
        class_uri: Full class URI

    Returns:
        Extracted class name
    """
    if '/' in class_uri:
        return class_uri.split('/')[-1]
    if '#' in class_uri:
        return class_uri.split('#')[-1]
    return class_uri


def print_top_attributes(attributes: list[dict[str, Any]]):
    """Print top attributes in a formatted table."""
    print("\n" + "="*120)
    print("TOP 25 ATTRIBUTES BY PATIENT COUNT")
    print("="*120)
    print(f"{'#':<4} {'Attribute Name':<30} {'Value':<25} {'Modifiers':<12} {'Patients':>10}")
    print("-"*120)

    for i, attr in enumerate(attributes, 1):
        modifiers = format_modifiers(attr['negated'], attr['uncertain'], attr['historic'])
        value_truncated = attr['value'][:24] + '...' if len(attr['value']) > 24 else attr['value']
        print(f"{i:<4} {attr['attribute_name']:<30} {value_truncated:<25} {modifiers:<12} {attr['num_patients']:>10,}")


def print_top_cancers(cancers: list[dict[str, Any]]):
    """Print top cancers in a formatted table."""
    print("\n" + "="*120)
    print("TOP 25 CANCERS BY PATIENT COUNT")
    print("="*120)
    print(f"{'#':<4} {'Cancer Type':<70} {'Modifiers':<12} {'Patients':>10}")
    print("-"*120)

    for i, cancer in enumerate(cancers, 1):
        modifiers = format_modifiers(cancer['negated'], cancer['uncertain'], cancer['historic'])
        cancer_name = extract_class_name(cancer['classUri'])
        print(f"{i:<4} {cancer_name:<70} {modifiers:<12} {cancer['num_patients']:>10,}")


def print_top_concepts(concepts: list[dict[str, Any]]):
    """Print top concepts in a formatted table."""
    print("\n" + "="*120)
    print("TOP 25 CONCEPTS BY PATIENT COUNT")
    print("="*120)
    print(f"{'#':<4} {'DPhe Group':<35} {'Class':<45} {'Neg':<5} {'Patients':>10}")
    print("-"*120)

    for i, concept in enumerate(concepts, 1):
        class_name = extract_class_name(concept['classUri'])
        neg_flag = "YES" if concept['negated'] else "NO"
        print(f"{i:<4} {concept['dpheGroup']:<35} {class_name:<45} {neg_flag:<5} {concept['num_patients']:>10,}")


def print_top_tumors(tumors: list[dict[str, Any]]):
    """Print top tumors in a formatted table."""
    print("\n" + "="*120)
    print("TOP 25 TUMORS BY PATIENT COUNT")
    print("="*120)
    print(f"{'#':<4} {'Tumor Type':<70} {'Modifiers':<12} {'Patients':>10}")
    print("-"*120)

    for i, tumor in enumerate(tumors, 1):
        modifiers = format_modifiers(tumor['negated'], tumor['uncertain'], tumor['historic'])
        tumor_name = extract_class_name(tumor['classUri'])
        print(f"{i:<4} {tumor_name:<70} {modifiers:<12} {tumor['num_patients']:>10,}")


def print_summary(attributes: list[dict[str, Any]],
                 cancers: list[dict[str, Any]],
                 concepts: list[dict[str, Any]],
                 tumors: list[dict[str, Any]]):
    """Print summary statistics."""
    print("\n" + "="*120)
    print("SUMMARY")
    print("="*120)

    if attributes:
        total_attr_patients = attributes[0]['num_patients']
        print(f"Most common attribute:  {attributes[0]['attribute_name']} = {attributes[0]['value']} ({total_attr_patients:,} patients)")

    if cancers:
        total_cancer_patients = cancers[0]['num_patients']
        cancer_name = extract_class_name(cancers[0]['classUri'])
        print(f"Most common cancer:     {cancer_name} ({total_cancer_patients:,} patients)")

    if concepts:
        total_concept_patients = concepts[0]['num_patients']
        print(f"Most common concept:    {concepts[0]['dpheGroup']} ({total_concept_patients:,} patients)")

    if tumors:
        total_tumor_patients = tumors[0]['num_patients']
        tumor_name = extract_class_name(tumors[0]['classUri'])
        print(f"Most common tumor:      {tumor_name} ({total_tumor_patients:,} patients)")

    print("="*120)


def main():
    """Main entry point."""
    # Determine database path
    script_dir = Path(__file__).resolve().parents[3]
    db_path = script_dir / "output" / "databases" / "individual" / "deepphe.sqlite3"

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("\nPlease run: python import_parsed_data.py")
        return 1

    print("="*120)
    print("TOP 25 ANALYSIS: Attributes, Cancers, Concepts, and Tumors by Patient Count")
    print("="*120)
    print(f"Database: {db_path}")

    # Connect to database
    conn = sqlite3.connect(str(db_path))

    try:
        # Get top 25 from each table
        print("\nQuerying database...")
        attributes = get_top_attributes(conn, limit=25)
        cancers = get_top_cancers(conn, limit=25)
        concepts = get_top_concepts(conn, limit=25)
        tumors = get_top_tumors(conn, limit=25)

        # Print results
        print_top_attributes(attributes)
        print_top_cancers(cancers)
        print_top_concepts(concepts)
        print_top_tumors(tumors)

        # Print summary
        print_summary(attributes, cancers, concepts, tumors)

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
