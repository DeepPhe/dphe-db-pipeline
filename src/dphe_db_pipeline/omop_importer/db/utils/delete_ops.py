from .db_dialect import is_sqlite_connection, table_ref
from .query_utils import execute_query


def truncate_table(cursor, conn, table_name, commit: bool = True):
    """
    Truncate a table.

    MySQL: TRUNCATE TABLE table;
    SQLite: DELETE FROM table;
            (Optional VACUUM/sequence reset is intentionally not done here)
    """
    tbl = table_ref(table_name)

    if is_sqlite_connection(conn):
        query = f"DELETE FROM {tbl};"
    else:
        query = f"TRUNCATE TABLE {tbl};"

    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


def drop_table(cursor, conn, table_name, commit: bool = True):
    """
    Drop a table if it exists.
    Works in both MySQL and SQLite.
    """
    tbl = table_ref(table_name)
    query = f"DROP TABLE IF EXISTS {tbl};"
    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)
