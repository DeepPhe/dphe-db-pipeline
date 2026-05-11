from .db_dialect import is_sqlite_connection, quote_ident
from .query_utils import execute_query


def loop_indexes(cursors, conns, config, before: bool = True):
    """
    Add indexes configured in config['before_update']['add_indexes'] or
    config['after_update']['add_indexes'].
    """
    key = "before_update" if before else "after_update"

    add_indexes = config.get(key, {}).get("add_indexes", [])
    for index in add_indexes:
        destination_schema = index.get("destination_schema", None)
        cursor = cursors[destination_schema]
        conn = conns[destination_schema]
        _add_index(cursor, conn, index)


def _normalize_index_name(destination_table: str, column: str) -> str:
    """
    Build a stable index name and keep it simple/portable.
    """
    # If caller passes dotted table, use the final segment for index naming.
    tbl_name = str(destination_table).split(".")[-1]
    col_name = str(column).split(".")[-1]
    return f"{tbl_name}_{col_name}_idx"


def add_index(cursor, conn, destination_table, column, key_length=255, commit: bool = False):
    """
    Add an index on a table if it doesn't already exist.

    Notes:
    - MySQL supports prefix indexes: INDEX(col(255))
    - SQLite does NOT support prefix lengths. We ignore key_length there.
    """
    index_name = _normalize_index_name(destination_table, column)

    if check_index_exists(cursor, conn, destination_table, index_name):
        print(f"Index {index_name} already exists on table {destination_table}. Skipping creation.")
        return

    q_table = quote_ident(destination_table)
    q_col = quote_ident(column)
    q_index = quote_ident(index_name)

    if is_sqlite_connection(conn):
        # SQLite: no prefix length syntax
        query = f"CREATE INDEX {q_index} ON {q_table} ({q_col});"
    else:
        # MySQL: optional prefix length for text columns
        if key_length is None or int(key_length) == 255:
            column_expr = f"({q_col})"
        else:
            column_expr = f"({q_col}({int(key_length)}))"
        query = f"CREATE INDEX {q_index} ON {q_table} {column_expr};"

    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


def check_index_exists(cursor, conn, destination_table, index_name, commit: bool = False):
    """
    Check if an index exists on a table.

    Returns:
        bool
    """
    if is_sqlite_connection(conn):
        # SQLite PRAGMA index_list(table) returns rows with index metadata.
        # Format varies a bit by sqlite version, but index name is usually row[1].
        bare_table = str(destination_table).split(".")[-1].strip().replace("`", "")
        cursor.execute(f"PRAGMA index_list({quote_ident(bare_table)});")
        rows = cursor.fetchall() or []

        for row in rows:
            # Common layouts:
            # (seq, name, unique, origin, partial)
            # (seq, name, unique)
            if len(row) > 1 and str(row[1]) == index_name:
                return True
        return False

    # MySQL path
    q_table = quote_ident(destination_table)
    query = f"SHOW INDEX FROM {q_table} WHERE Key_name = %s;"
    cursor.execute(query, (index_name,))
    return cursor.fetchone() is not None


def _add_index(cursor, conn, index):
    """
    Add one index config entry, which may target one table or multiple tables.
    """
    destination_table = index.get("destination_table", None)
    destination_tables = index.get("destination_tables", None)
    column = index["destination_column"]
    key_length = index.get("key_length", 255)

    if destination_tables is not None:
        tables = [t.strip() for t in str(destination_tables).split(",") if t.strip()]
        for table in tables:
            add_index(cursor, conn, table, column, key_length, commit=True)
    else:
        add_index(cursor, conn, destination_table, column, key_length, commit=True)


def add_indexes_before_insert(cursors, config, conns):
    """
    Public wrapper to add configured indexes before insert/update phase.
    """
    loop_indexes(cursors, conns, config, before=True)


def add_indexes_after_insert(cursors, config, conns):
    """
    Public wrapper to add configured indexes after insert/update phase.
    """
    loop_indexes(cursors, conns, config, before=False)