import os
import csv
import sqlite3

from .delete_ops import drop_table
from .query_utils import execute_many_query, execute_query


def _insert_csv_batch(cursor, conn, destination_table, headers, data, commit=False):
    """
    Insert a batch of CSV data into a table.
    """
    # Check if we're using SQLite or MySQL based on the connection type
    is_sqlite = isinstance(conn, sqlite3.Connection)

    if is_sqlite:
        # SQLite uses ? as parameter placeholder
        insert_sql = f"INSERT INTO `{destination_table}` ({', '.join([f'`{h}`' for h in headers])}) VALUES ({', '.join(['?'] * len(headers))})"
    else:
        # MySQL uses %s as parameter placeholder
        insert_sql = f"INSERT INTO `{destination_table}` ({', '.join([f'`{h}`' for h in headers])}) VALUES ({', '.join(['%s'] * len(headers))})"

    execute_many_query(cursor, conn, insert_sql, data, commit)


def process_a_csv_file(cursor, conn, csv_path, batch_size=50000):
    """
    Process a CSV file by creating a table based on its name and headers, then inserting the data.
    """
    destination_table = os.path.splitext(os.path.basename(csv_path))[0]
    print(f"Processing file: {csv_path} into table: {destination_table}")

    # Read header row
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)

    columns_definition = ", ".join([f"`{col}` TEXT" for col in headers])

    # Drop the table if it exists
    drop_table(cursor, conn, destination_table, commit=True)

    query = f"CREATE TABLE IF NOT EXISTS `{destination_table}` ({columns_definition})"
    execute_query(cursor=cursor, conn=conn, query=query, commit=True)

    #get line count of csv
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        line_count = sum(1 for _ in csvfile)
        print(f"Total lines in CSV: {line_count}")


    # Insert data in batches
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        data = []
        batch_number = 0
        print(f"Inserting {line_count // batch_size} batches into {destination_table}, {batch_size} inserts at a time:")
        for row in reader:
            data.append(row)
            if len(data) >= batch_size:
                if batch_number != 0 and batch_number % 10 == 0:
                    print()
                _insert_csv_batch(cursor, conn=conn, destination_table=destination_table, headers=headers, data=data, commit=True)
                print(f"{batch_number:04d}", end=", ")
                batch_number += 1

                data = []
        if data:
            _insert_csv_batch(cursor, conn, destination_table, headers, data, commit=True)
            print(batch_number, end=", ")

        conn.commit()
        print("\nData insertion completed.")

        #appened to a process.log file that the table was written
        with open('process.log', 'a') as log_file:
            log_file.write(f"Processed file: {csv_path} into table: {destination_table}\n")
