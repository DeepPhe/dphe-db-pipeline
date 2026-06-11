import sqlite3
from typing import Any

from .query_utils import execute_query

# ---------------------------------------------------------------------------
# Dialect helpers (kept local so this file works immediately)
# ---------------------------------------------------------------------------

def _is_sqlite(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


def _placeholder(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _strip_schema_for_sqlite(table_name: str) -> str:
    """
    SQLite doesn't support db.schema.table notation in the same way MySQL does.
    If a schema-qualified table name is passed, use the last segment.
    """
    if "." in table_name:
        return table_name.split(".")[-1]
    return table_name


def _quote_ident(name: str) -> str:
    # Consistent identifier quoting across SQLite/MySQL for simple identifiers.
    # (Backticks work in both for this use case.)
    return f"`{name}`"


def _qualify_table(conn, schema: str | None, table: str) -> str:
    table = _strip_schema_for_sqlite(table) if _is_sqlite(conn) else table
    if _is_sqlite(conn) or not schema:
        return _quote_ident(table)
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _normalize_default_sql(dest_default: Any) -> str:
    """
    Convert mapping default value into SQL literal.
    Preserves SQL NULL and CURRENT_TIMESTAMP-style literals when appropriate.
    """
    if dest_default is None:
        return "NULL"

    if not isinstance(dest_default, str):
        # numeric / bool etc
        return str(dest_default)

    raw = dest_default.strip()
    upper = raw.upper()

    if upper in {"NULL", "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME"}:
        return upper

    # numeric strings should not be quoted
    try:
        float(raw)
        return raw
    except ValueError:
        pass

    escaped = raw.replace("'", "''")
    return f"'{escaped}'"


def _safe_sqlite_temp_table_name(base: str = "temp_agg") -> str:
    # deterministic and compatible
    return f"{base}"


def _sqlite_concat_ws_dash(cols: list[str], table_alias: str = "s") -> str:
    """
    Emulate CONCAT_WS('-', ...) in SQLite.
    We only call this when all source columns are non-null/non-empty.
    """
    if not cols:
        return "NULL"
    expr = f"{table_alias}.{_quote_ident(cols[0])}"
    for col in cols[1:]:
        expr = f"({expr} || '-' || {table_alias}.{_quote_ident(col)})"
    return expr


def _table_exists(cursor, conn, table_name: str) -> bool:
    if _is_sqlite(conn):
        t = _strip_schema_for_sqlite(table_name)
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1;",
            (t,),
        )
        return cursor.fetchone() is not None
    else:
        # MySQL will error if schema-qualified in SHOW TABLES LIKE; keep simple
        cursor.execute(f"SHOW TABLES LIKE '{table_name}';")
        return cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# Column metadata helpers
# ---------------------------------------------------------------------------

def get_column_type(cursor, conn, table_name, column_name):
    """
    Get the current data type of a column in a table.

    Returns:
        str | None
    """
    if _is_sqlite(conn):
        table_name = _strip_schema_for_sqlite(table_name)
        cursor.execute(f"PRAGMA table_info({_quote_ident(table_name)});")
        for row in cursor.fetchall():
            # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
            if row[1] == column_name:
                return row[2]
        return None

    query = f"SHOW COLUMNS FROM {_quote_ident(table_name)} WHERE Field = '{column_name}';"
    cursor.execute(query)
    result = cursor.fetchone()
    return result[1] if result else None


def change_column_type(cursor, conn, table_name, column_name, new_type, commit=False):
    """
    Change a column type.
    SQLite implementation rebuilds the table.
    """
    if _is_sqlite(conn):
        table_name = _strip_schema_for_sqlite(table_name)

        cursor.execute(f"PRAGMA table_info({_quote_ident(table_name)});")
        columns = cursor.fetchall()
        if not columns:
            raise RuntimeError(f"Table not found: {table_name}")

        new_table = f"{table_name}_new"

        column_defs = []
        col_names = []
        for col in columns:
            col_name = col[1]
            col_type = new_type if col_name == column_name else (col[2] or "TEXT")
            not_null = "NOT NULL" if col[3] == 1 else ""
            default = ""
            if col[4] is not None:
                # PRAGMA dflt_value is already SQL literal in SQLite metadata
                default = f"DEFAULT {col[4]}"
            pk = "PRIMARY KEY" if col[5] == 1 else ""
            column_defs.append(
                " ".join(part for part in [f"{_quote_ident(col_name)}", col_type, not_null, default, pk] if part)
            )
            col_names.append(_quote_ident(col_name))

        create_sql = f"CREATE TABLE {_quote_ident(new_table)} ({', '.join(column_defs)});"
        cursor.execute(create_sql)

        cols_csv = ", ".join(col_names)
        cursor.execute(
            f"INSERT INTO {_quote_ident(new_table)} ({cols_csv}) "
            f"SELECT {cols_csv} FROM {_quote_ident(table_name)};"
        )
        cursor.execute(f"DROP TABLE {_quote_ident(table_name)};")
        cursor.execute(f"ALTER TABLE {_quote_ident(new_table)} RENAME TO {_quote_ident(table_name)};")

        if commit:
            conn.commit()
        return

    query = f"ALTER TABLE {_quote_ident(table_name)} MODIFY COLUMN {_quote_ident(column_name)} {new_type};"
    execute_query(cursor, conn, query, commit)


# ---------------------------------------------------------------------------
# Column creation helpers
# ---------------------------------------------------------------------------

def create_destination_column(cursor, conn, mapping):
    """
    Create the destination column if it does not already exist.
    Expected mapping keys:
      destination_table, destination_column, destination_column_type,
      destination_column_default, destination_column_nullable, destination_column_index
    """
    dest_schema = mapping.get("destination_schema", None)
    dest_table = mapping["destination_table"]
    dest_column = mapping["destination_column"]
    dest_type = mapping["destination_column_type"]
    dest_default = mapping.get("destination_column_default", "NULL")
    dest_nullable = mapping.get("destination_column_nullable", "YES")
    dest_index = mapping.get("destination_column_index", "NO")

    # SQLite ignores schema qualification
    if column_exists(cursor, conn, dest_table, dest_column):
        print(f"Column '{dest_column}' already exists in table '{dest_table}'.")
        return

    table_sql = _qualify_table(conn, dest_schema, dest_table)
    default_sql = _normalize_default_sql(dest_default)
    nullability = "NULL" if str(dest_nullable).upper() == "YES" else "NOT NULL"

    # SQLite supports only limited ALTER TABLE ADD COLUMN constraints, but this is okay.
    if _is_sqlite(conn):
        alter_sql = (
            f"ALTER TABLE {table_sql} "
            f"ADD COLUMN {_quote_ident(dest_column)} {dest_type} {nullability} DEFAULT {default_sql};"
        )
    else:
        alter_sql = (
            f"ALTER TABLE {table_sql} "
            f"ADD COLUMN {_quote_ident(dest_column)} {dest_type} DEFAULT {default_sql} {nullability};"
        )

    print(f"Creating column with SQL: {alter_sql}")
    cursor.execute(alter_sql)

    if str(dest_index).upper() == "YES":
        # Avoid illegal characters in index name if schema/table names contain dots
        safe_table = dest_table.replace(".", "_")
        index_name = f"idx_{safe_table}_{dest_column}"
        if _is_sqlite(conn):
            index_sql = (
                f"CREATE INDEX IF NOT EXISTS {_quote_ident(index_name)} "
                f"ON {_quote_ident(_strip_schema_for_sqlite(dest_table))} ({_quote_ident(dest_column)});"
            )
        else:
            index_sql = (
                f"CREATE INDEX {_quote_ident(index_name)} "
                f"ON {table_sql} ({_quote_ident(dest_column)});"
            )
        print(f"Creating index with SQL: {index_sql}")
        try:
            cursor.execute(index_sql)
        except Exception as e:
            # Don't hard-fail column creation if index already exists / name collision
            print(f"Warning: failed to create index {index_name}: {e}")

    conn.commit()


def create_table_for_column(cursor, conn, destination_table, dest_schema, commit=False):
    """
    Ensure a table exists for column updates (with a primary key).
    """
    if _is_sqlite(conn):
        destination_table = _strip_schema_for_sqlite(destination_table)
        query = f"""
        CREATE TABLE IF NOT EXISTS {_quote_ident(destination_table)} (
            id INTEGER PRIMARY KEY
        );
        """
    else:
        table_sql = _qualify_table(conn, dest_schema, destination_table)
        query = f"""
        CREATE TABLE IF NOT EXISTS {table_sql} (
            id INT AUTO_INCREMENT PRIMARY KEY
        );
        """

    return execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


def column_exists(cursor, conn, destination_table, destination_column):
    """
    Check if a column exists in a table.
    """
    if _is_sqlite(conn):
        destination_table = _strip_schema_for_sqlite(destination_table)
        cursor.execute(f"PRAGMA table_info({_quote_ident(destination_table)});")
        for col in cursor.fetchall():
            if col[1] == destination_column:
                return True
        return False

    query = f"SHOW COLUMNS FROM {_quote_ident(destination_table)} WHERE Field = '{destination_column}';"
    cursor.execute(query)
    return cursor.fetchone() is not None


def add_column(
    cursor,
    conn,
    destination_table,
    destination_column,
    destination_column_type,
    destination_column_default,
    destination_column_nullable,
    commit=False,
):
    """
    Add a column if it doesn't already exist.
    """
    if column_exists(cursor, conn, destination_table, destination_column):
        print(f"Column {destination_column} already exists in table {destination_table}. Skipping creation.")
        return

    nullability = "NULL" if str(destination_column_nullable).upper() == "YES" else "NOT NULL"
    default_sql = _normalize_default_sql(destination_column_default)

    if _is_sqlite(conn):
        destination_table = _strip_schema_for_sqlite(destination_table)
        query = f"""
        ALTER TABLE {_quote_ident(destination_table)}
        ADD COLUMN {_quote_ident(destination_column)} {destination_column_type}
        {nullability} DEFAULT {default_sql};
        """
    else:
        query = f"""
        ALTER TABLE {_quote_ident(destination_table)}
        ADD COLUMN {_quote_ident(destination_column)} {destination_column_type}
        DEFAULT {default_sql}
        {nullability};
        """

    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


# ---------------------------------------------------------------------------
# Update helpers
# ---------------------------------------------------------------------------

def update_column_with_join(
    cursor,
    conn,
    destination_table,
    destination_column,
    source_schema,
    source_tables,
    source_columns,
    join_on,
    commit=False,
):
    """
    Update destination_column by aggregating values across multiple source tables, grouped by join_on.

    MySQL path:
      - temp table + UPDATE ... JOIN + CONCAT_WS
    SQLite path:
      - temp table + correlated UPDATE + || concatenation
    """
    if isinstance(source_tables, str):
        source_tables = [t.strip() for t in source_tables.split(",") if t.strip()]
    else:
        source_tables = [str(t).strip() for t in source_tables if str(t).strip()]

    source_columns = [str(c).strip() for c in source_columns if str(c).strip()]
    if not source_tables:
        print("No source_tables provided. Skipping update_column_with_join.")
        return
    if not source_columns:
        print("No source_columns provided. Skipping update_column_with_join.")
        return

    is_sqlite = _is_sqlite(conn)
    src_schema = None if is_sqlite else source_schema
    dest_tbl = _strip_schema_for_sqlite(destination_table) if is_sqlite else destination_table

    # Build UNION ALL over source tables
    subqueries = []
    for tbl in source_tables:
        tbl_sql = _qualify_table(conn, src_schema, tbl)
        cols_sql = ", ".join(_quote_ident(col) for col in source_columns)
        subqueries.append(
            f"SELECT {_quote_ident(join_on)} AS {_quote_ident(join_on)}, {cols_sql} FROM {tbl_sql}"
        )
    union_subquery = " UNION ALL ".join(subqueries)

    aggregation_query = (
        f"SELECT {_quote_ident(join_on)}, "
        + ", ".join(f"MIN({_quote_ident(col)}) AS {_quote_ident(col)}" for col in source_columns)
        + f" FROM ({union_subquery}) AS sub GROUP BY {_quote_ident(join_on)}"
    )

    temp_table = _safe_sqlite_temp_table_name("temp_agg")

    # Create temp table
    if is_sqlite:
        execute_query(cursor, conn, f"DROP TABLE IF EXISTS {_quote_ident(temp_table)};", commit=False)
        create_temp_table = f"CREATE TEMP TABLE {_quote_ident(temp_table)} AS {aggregation_query};"
    else:
        execute_query(cursor, conn, f"DROP TEMPORARY TABLE IF EXISTS {_quote_ident(temp_table)};", commit=False)
        create_temp_table = f"CREATE TEMPORARY TABLE {_quote_ident(temp_table)} AS {aggregation_query};"

    execute_query(cursor, conn, create_temp_table, commit=False)

    # Build conditional / concatenation
    if is_sqlite:
        conditions = " AND ".join(
            f"s.{_quote_ident(col)} IS NOT NULL AND TRIM(CAST(s.{_quote_ident(col)} AS TEXT)) <> ''"
            for col in source_columns
        )
        concat_expr = _sqlite_concat_ws_dash(source_columns, table_alias="s")

        update_query = f"""
        UPDATE {_quote_ident(dest_tbl)} AS t
        SET {_quote_ident(destination_column)} = (
            SELECT CASE
                     WHEN {conditions} THEN {concat_expr}
                     ELSE NULL
                   END
            FROM {_quote_ident(temp_table)} AS s
            WHERE s.{_quote_ident(join_on)} = t.{_quote_ident(join_on)}
        )
        WHERE EXISTS (
            SELECT 1
            FROM {_quote_ident(temp_table)} AS s
            WHERE s.{_quote_ident(join_on)} = t.{_quote_ident(join_on)}
        );
        """
    else:
        conditions = " AND ".join(
            f"s.{_quote_ident(col)} IS NOT NULL AND s.{_quote_ident(col)} <> ''"
            for col in source_columns
        )
        concatenation = ", ".join(f"s.{_quote_ident(col)}" for col in source_columns)

        update_query = f"""
        UPDATE {_quote_ident(dest_tbl)} t
        JOIN {_quote_ident(temp_table)} s ON t.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
        SET t.{_quote_ident(destination_column)} = CASE
            WHEN {conditions} THEN CONCAT_WS('-', {concatenation})
            ELSE NULL
        END
        WHERE TRUE;
        """

    execute_query(cursor, conn, update_query, commit=False)

    # Drop temp table
    if is_sqlite:
        execute_query(cursor, conn, f"DROP TABLE IF EXISTS {_quote_ident(temp_table)};", commit=False)
    else:
        execute_query(cursor, conn, f"DROP TEMPORARY TABLE IF EXISTS {_quote_ident(temp_table)};", commit=False)

    if commit:
        conn.commit()


def update_single_column(
    cursor,
    conn,
    destination_table,
    destination_column,
    destination_column_type,
    source_schema,
    source_column,
    source_table,
    join_on,
    commit=False,
):
    """
    Update a single column from a source table using join_on.
    SQLite-safe and MySQL-safe.
    """
    is_sqlite = _is_sqlite(conn)
    dest_tbl = _strip_schema_for_sqlite(destination_table) if is_sqlite else destination_table
    src_tbl_sql = _qualify_table(conn, None if is_sqlite else source_schema, source_table)

    if str(destination_column_type).upper() == "DATE":
        if is_sqlite:
            # SQLite doesn't support UPDATE ... JOIN
            query = f"""
            UPDATE {_quote_ident(dest_tbl)} AS d
            SET {_quote_ident(destination_column)} = (
              SELECT date(s.{_quote_ident(source_column)})
              FROM {src_tbl_sql} AS s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
              LIMIT 1
            )
            WHERE EXISTS (
              SELECT 1
              FROM {src_tbl_sql} AS s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
            );
            """
        else:
            query = f"""
            UPDATE {_quote_ident(dest_tbl)} d
            SET d.{_quote_ident(destination_column)} = (
              SELECT CAST(s.{_quote_ident(source_column)} AS DATE)
              FROM {src_tbl_sql} s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
              LIMIT 1
            )
            WHERE EXISTS (
              SELECT 1
              FROM {src_tbl_sql} s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
            );
            """
    else:
        if is_sqlite:
            query = f"""
            UPDATE {_quote_ident(dest_tbl)} AS d
            SET {_quote_ident(destination_column)} = (
              SELECT s.{_quote_ident(source_column)}
              FROM {src_tbl_sql} AS s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
              LIMIT 1
            )
            WHERE EXISTS (
              SELECT 1
              FROM {src_tbl_sql} AS s
              WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
            );
            """
        else:
            query = f"""
            UPDATE {_quote_ident(dest_tbl)} d
            JOIN {src_tbl_sql} s
              ON d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
            SET d.{_quote_ident(destination_column)} = s.{_quote_ident(source_column)};
            """

    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


def insert_single_column_from_muitlple_columns(
    cursor,
    conn,
    destination_table,
    destination_column,
    destination_column_type,
    source_schema,
    source_columns,
    source_tables,
    join_on,
    commit=False,
):
    """
    Insert distinct values into destination_table.destination_column from multiple source columns/tables.

    Note: function name preserved for backward compatibility (typo in original).
    """
    is_sqlite = _is_sqlite(conn)

    if len(source_columns) != len(source_tables):
        raise ValueError("source_columns and source_tables must have the same length")

    unions = []
    for col, tbl in zip(source_columns, source_tables, strict=True):
        tbl_sql = _qualify_table(conn, None if is_sqlite else source_schema, tbl)
        unions.append(f"SELECT {_quote_ident(col)} AS {_quote_ident(destination_column)} FROM {tbl_sql}")

    union_sql = " UNION ".join(unions)
    dest_tbl = _strip_schema_for_sqlite(destination_table) if is_sqlite else destination_table

    query = f"""
    INSERT INTO {_quote_ident(dest_tbl)} ({_quote_ident(destination_column)})
    SELECT DISTINCT {_quote_ident(destination_column)}
    FROM ({union_sql}) AS col_union
    WHERE {_quote_ident(destination_column)} IS NOT NULL;
    """
    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


def insert_single_column(
    cursor,
    conn,
    destination_table,
    destination_column,
    destination_column_type,
    source_schema,
    source_column,
    source_table,
    join_on,
    commit=False,
):
    """
    Insert values from source_table.source_column into destination_table.destination_column
    where join_on does not already exist in destination.
    """
    is_sqlite = _is_sqlite(conn)
    dest_tbl = _strip_schema_for_sqlite(destination_table) if is_sqlite else destination_table
    src_tbl_sql = _qualify_table(conn, None if is_sqlite else source_schema, source_table)

    query = f"""
    INSERT INTO {_quote_ident(dest_tbl)} ({_quote_ident(destination_column)})
    SELECT s.{_quote_ident(source_column)}
    FROM {src_tbl_sql} s
    WHERE NOT EXISTS (
        SELECT 1
        FROM {_quote_ident(dest_tbl)} d
        WHERE d.{_quote_ident(join_on)} = s.{_quote_ident(join_on)}
    );
    """
    execute_query(cursor=cursor, conn=conn, query=query, commit=commit)


# ---------------------------------------------------------------------------
# ICD utility
# ---------------------------------------------------------------------------

def get_unique_matching_icd_codes(
    cursor,
    table_name,
    column_name,
    where_values_in_array=None,
    icd_vocab=None,
    substring_char=None,
    index=None,
):
    """
    Get unique values for a column, optionally filtering for ICD vocab and post-processing substrings.
    SQLite-safe fallback for SUBSTRING_INDEX.
    """
    # Keep behavior compatible with original, but fix uninitialized column_string bug.
    column_expr = column_name

    is_sqlite = False
    try:
        is_sqlite = isinstance(getattr(cursor, "connection", None), sqlite3.Connection)
    except Exception:
        pass

    # If substring requested and running MySQL, use SUBSTRING_INDEX; otherwise post-process in Python
    use_python_substring = bool(substring_char)

    if substring_char and not is_sqlite:
        # MySQL supports SUBSTRING_INDEX
        if index is None:
            index = -1
        column_expr = f"SUBSTRING_INDEX({column_name}, '{substring_char}', {index})"
        use_python_substring = False

    query = f"SELECT DISTINCT {column_expr} FROM {table_name}"
    conditions = []

    if icd_vocab:
        conditions.append(f"{column_name} LIKE '%{icd_vocab}%'")

    if where_values_in_array:
        vals = ", ".join("'" + str(v).replace("'", "''") + "'" for v in where_values_in_array)
        conditions.append(f"{column_name} IN ({vals})")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor.execute(query)
    values = [row[0] for row in cursor.fetchall() if row and row[0] is not None]

    if use_python_substring and substring_char:
        processed = []
        for v in values:
            s = str(v)
            parts = s.split(substring_char)
            if index is None:
                processed.append(parts[-1])
            else:
                try:
                    processed.append(parts[index])
                except Exception:
                    processed.append(s)
        values = processed

    # preserve uniqueness
    return list(dict.fromkeys(values))
