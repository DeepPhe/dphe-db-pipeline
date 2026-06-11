#!/usr/bin/env python3
"""
Script to create and populate the concepts table in the deepphe_100 SQLite database.
"""

import os
import sqlite3


def create_concepts_table(db_path):
    """
    Connect to the SQLite database and create the concepts table.

    Args:
        db_path: Path to the SQLite database file
    """
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Warning: Database file '{db_path}' does not exist. It will be created.")

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the concepts table
    # Drop table if it exists (optional - comment out if you want to preserve existing data)
    # cursor.execute("DROP TABLE IF EXISTS concepts")

    create_table_query = """
    CREATE TABLE IF NOT EXISTS concepts (
        patientid TEXT NOT NULL,
        cancerid TEXT NOT NULL,
        concept_description TEXT NOT NULL,
        concept_category TEXT,
        concept_status TEXT,
        attribute_value TEXT,
        attribute_name TEXT
    )
    """

    cursor.execute(create_table_query)
    conn.commit()

    print("✓ Table 'concepts' created successfully!")

    return conn, cursor


def insert_example_data(cursor, conn):
    """
    Insert the example data into the concepts table.

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    example_data = [
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', '', 'Location'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', 'Axilla', 'Location'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', 'Lower-Outer Quadrant of the Breast', 'Location'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', 'C50', 'Topography, major'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', 'Left', 'Laterality'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', 'Right', 'Laterality'),
        ('fake_patient1', 'fake_patient1_07072025191757_C_106_C', 'Breast Lobular Carcinoma In Situ', 'Neoplasm', 'Historical', '5', 'Topography, minor'),
    ]

    insert_query = """
    INSERT INTO concepts (patientid, cancerid, concept_description, concept_category,
                         concept_status, attribute_value, attribute_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    cursor.executemany(insert_query, example_data)
    conn.commit()

    print(f"✓ Inserted {len(example_data)} example records into the concepts table!")


def display_table_info(cursor):
    """
    Display information about the concepts table.

    Args:
        cursor: Database cursor
    """
    # Get table schema
    cursor.execute("PRAGMA table_info(concepts)")
    columns = cursor.fetchall()

    print("\n" + "="*60)
    print("Table Schema:")
    print("="*60)
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    # Get row count
    cursor.execute("SELECT COUNT(*) FROM concepts")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows in table: {count}")

    # Display first few rows
    if count > 0:
        print("\n" + "="*60)
        print("Sample Data (first 5 rows):")
        print("="*60)
        cursor.execute("SELECT * FROM concepts LIMIT 5")
        rows = cursor.fetchall()

        for row in rows:
            print(f"  Patient: {row[0]}")
            print(f"  Cancer ID: {row[1]}")
            print(f"  Description: {row[2]}")
            print(f"  Category: {row[3]}")
            print(f"  Status: {row[4]}")
            print(f"  Attribute Value: {row[5]}")
            print(f"  Attribute Name: {row[6]}")
            print("  " + "-"*56)


def main():
    """Main function to create table and optionally insert example data."""
    db_path = "deepphe_100"

    print(f"Connecting to database: {db_path}")
    print("="*60)

    # Create the table
    conn, cursor = create_concepts_table(db_path)

    # Ask user if they want to insert example data
    response = input("\nDo you want to insert example data? (y/n): ").strip().lower()
    if response in ['y', 'yes']:
        insert_example_data(cursor, conn)

    # Display table information
    display_table_info(cursor)

    # Close the connection
    conn.close()
    print("\n✓ Database connection closed.")


if __name__ == "__main__":
    main()

