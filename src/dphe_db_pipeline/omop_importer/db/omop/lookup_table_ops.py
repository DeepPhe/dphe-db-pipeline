import csv
import os
import sqlite3

from ..utils.column_ops import create_destination_column
from ..utils.delete_ops import drop_table
from ..utils.indexing_ops import add_index
from ..utils.query_utils import execute_many_query, execute_query


def _is_sqlite(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


def _quote_ident(name: str) -> str:
    return f"`{str(name).replace('`', '``')}`"


def _insert_placeholders(conn, ncols: int) -> str:
    ph = "?" if _is_sqlite(conn) else "%s"
    return ", ".join([ph] * ncols)


def _get_all_files_in_directory(directory):
    """
    Get all files in a directory.
    """
    files = []
    for root, _dirs, filenames in os.walk(directory):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files


def _insert_data(cursor, conn, lookup_table_files, destination_table):
    for lookup_table_file in lookup_table_files:
        with open(lookup_table_file, encoding="utf-8", newline="") as file:
            # Preserving original behavior from your file
            delimiter = "\t" if lookup_table_file.endswith(".csv") else "|"
            reader = csv.reader(file, delimiter=delimiter)
            headers = next(reader)  # Skip header row

            # Create table if it doesn't exist
            create_table_query = f"CREATE TABLE IF NOT EXISTS {_quote_ident(destination_table)} ("
            for header in headers:
                create_table_query += f"{_quote_ident(header)} TEXT, "
            create_table_query = create_table_query.rstrip(", ") + ");"
            execute_query(cursor=cursor, conn=conn, query=create_table_query, commit=True)

            # Insert data in batches
            batch_size = 50000
            batch = []
            total_rows = 0

            columns_sql = ", ".join(_quote_ident(h) for h in headers)
            values_sql = _insert_placeholders(conn, len(headers))
            insert_sql = (
                f"INSERT INTO {_quote_ident(destination_table)} ({columns_sql}) "
                f"VALUES ({values_sql})"
            )

            for row in reader:
                # normalize malformed rows
                if len(row) < len(headers):
                    row = row + [""] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    row = row[:len(headers)]

                batch.append(tuple(row))

                if len(batch) >= batch_size:
                    execute_many_query(cursor, conn, insert_sql, batch, commit=True)
                    total_rows += len(batch)
                    print(f"Inserted batch: {total_rows} rows into {destination_table}")
                    batch = []

            # Insert any remaining rows
            if batch:
                execute_many_query(cursor, conn, insert_sql, batch, commit=True)
                total_rows += len(batch)

            print(f"Data inserted into {destination_table} from {lookup_table_file}. Total rows: {total_rows}")


def create_lookup_tables(cursors, conns, config):
    """
    Create a lookup table with the specified column definitions.
    """
    lookup_schema = config["lookup_schema"]
    lookup_tables_dir = config["lookup_tables_dir"]
    subdirectories = config["subdirectories"]

    cursor = cursors[lookup_schema]
    conn = conns[lookup_schema]

    for subdirectory in subdirectories:
        directory = subdirectory["directory"]

        # rebuild from files
        drop_table(cursor, conn, directory, True)

        lookup_table_files = _get_all_files_in_directory(os.path.join(lookup_tables_dir, directory))
        columns = subdirectory["columns"]
        destination_table = directory

        _insert_data(cursor, conn, lookup_table_files, destination_table)

        # Add indexes / destination columns if specified in config
        for column in columns:
            destination_column = column["destination_column"]
            column["destination_table"] = destination_table
            create_destination_column(cursor, conn, column)

            destination_column_index = column.get("destination_column_index", "NO")
            if destination_column_index == "YES":
                add_index(
                    cursor,
                    conn,
                    destination_table,
                    destination_column,
                    key_length=column.get("key_length", 255),
                    commit=True,
                )
                print(f"Index on {destination_column} created successfully.")
