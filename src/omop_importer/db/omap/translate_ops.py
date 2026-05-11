import sqlite3

from ..utils.column_ops import create_destination_column

# --------------------- Translation Tasks ---------------------
from ...omap_mappers.demographics import (
    get_gender_readable,
    get_race_readable,
    get_ethnicity_readable,
)


def _is_sqlite(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


def _placeholder(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _quote_ident(name: str) -> str:
    return f"`{name}`"


def _strip_schema_for_sqlite(table_name: str) -> str:
    return table_name.split(".")[-1] if "." in table_name else table_name


def _qualify_table(conn, schema, table):
    if _is_sqlite(conn):
        return _quote_ident(_strip_schema_for_sqlite(table))
    if schema:
        return f"{_quote_ident(schema)}.{_quote_ident(table)}"
    return _quote_ident(table)


def _get_translator(concept):
    """
    Return the appropriate translator function for a given concept.
    """
    concept = str(concept).upper()
    if concept == "GENDER":
        return get_gender_readable
    elif concept == "RACE":
        return get_race_readable
    elif concept == "ETHNICITY":
        return get_ethnicity_readable
    else:
        return lambda x: "Unknown"


def _safe_translate_value(translator, source_value):
    """
    Preserve old behavior (translate int concept IDs) but avoid crashing on NULL/blank/non-int values.
    """
    if source_value is None:
        return None

    if isinstance(source_value, str) and source_value.strip() == "":
        return None

    try:
        translated_value = translator(int(source_value))
    except (TypeError, ValueError):
        # If source is not numeric, fall back to raw translator call or string
        try:
            translated_value = translator(source_value)
        except Exception:
            translated_value = "Unknown"

    return translated_value


def _sqlite_same_db(conn_a, conn_b) -> bool:
    """
    Best-effort check whether two sqlite connections point to the same main DB file.
    """
    if not (_is_sqlite(conn_a) and _is_sqlite(conn_b)):
        return False
    try:
        a = conn_a.execute("PRAGMA database_list").fetchall()
        b = conn_b.execute("PRAGMA database_list").fetchall()
        # rows: seq, name, file
        a_main = next((row[2] for row in a if len(row) >= 3 and row[1] == "main"), None)
        b_main = next((row[2] for row in b if len(row) >= 3 and row[1] == "main"), None)
        return bool(a_main and b_main and a_main == b_main)
    except Exception:
        return False


def _set_sqlite_session_pragmas(conn):
    """
    Reduce lock errors for long-running mixed read/write jobs.
    Safe no-op for non-SQLite callers (caller checks type).
    """
    try:
        conn.execute("PRAGMA busy_timeout = 30000;")   # wait up to 30s on locks
        # WAL often improves read/write concurrency; ignore if unsupported.
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass


def process_translation(cursors, conns, config):
    """
    Process each translation mapping defined in the JSON config.

    SQLite-safe rewrite:
      - avoids MySQL-only UPDATE ... JOIN syntax in SQLite mode
      - uses correct placeholders (? vs %s)
      - safely handles NULL/non-numeric source values
      - avoids long-held write locks by committing per source table in SQLite mode
      - reuses destination cursor as source cursor when both SQLite connections target same DB
    """
    mappings = config.get("after_update", {}).get("translate_concepts", [])
    if not mappings:
        print("No translation mappings found under after_update.translate_concepts")
        return

    for mapping in mappings:
        source_tables_raw = mapping["source_tables"]
        source_schema = mapping.get("source_schema")
        dest_table = mapping["destination_table"]
        dest_column = mapping["destination_column"]
        dest_schema = mapping.get("destination_schema")
        source_column = mapping["source_column"]
        concept = mapping["concept"]

        # Destination DB connection/cursor drives the UPDATE
        dest_cursor = cursors[dest_schema]
        dest_conn = conns[dest_schema]

        # Source may be same connection, but allow different schema/cursor dict entry if present
        source_cursor = cursors.get(source_schema, dest_cursor)
        source_conn = conns.get(source_schema, dest_conn)

        if _is_sqlite(dest_conn):
            _set_sqlite_session_pragmas(dest_conn)
        if _is_sqlite(source_conn):
            _set_sqlite_session_pragmas(source_conn)

        # If source/dest are separate sqlite connections but same DB file,
        # force reads through the destination cursor/connection to avoid lock churn.
        if _sqlite_same_db(source_conn, dest_conn):
            source_conn = dest_conn
            source_cursor = dest_cursor

        translator = _get_translator(concept)

        # Ensure destination column exists once per mapping
        create_destination_column(dest_cursor, dest_conn, mapping)

        # Commit DDL immediately in SQLite to release schema/write lock before reads
        if _is_sqlite(dest_conn):
            try:
                dest_conn.commit()
            except Exception:
                pass

        source_tables = [t.strip() for t in str(source_tables_raw).split(",") if t.strip()]
        if not source_tables:
            print(f"No source tables for translation mapping: {mapping}")
            continue

        for source_table in source_tables:
            print(
                f"Translating {concept}: {source_table}.{source_column} "
                f"--> {dest_table}.{dest_column}"
            )

            src_table_sql = _qualify_table(source_conn, source_schema, source_table)
            dest_table_sql = _qualify_table(dest_conn, dest_schema, dest_table)

            # If using separate sqlite connections, ensure no open write txn before read
            if _is_sqlite(dest_conn) and source_conn is not dest_conn:
                try:
                    dest_conn.commit()
                except Exception:
                    pass

            # Distinct source values from source table
            distinct_sql = (
                f"SELECT DISTINCT {_quote_ident(source_column)} "
                f"FROM {src_table_sql};"
            )
            source_cursor.execute(distinct_sql)
            distinct_values = source_cursor.fetchall()

            ph = _placeholder(dest_conn)

            for row in distinct_values:
                if not row:
                    continue
                source_value = row[0]

                translated_value = _safe_translate_value(translator, source_value)
                if translated_value is None:
                    # Skip NULL/blank values instead of crashing
                    continue

                print(
                    f"Updating rows where {source_column} = {source_value!r} "
                    f"to {translated_value!r}"
                )

                if _is_sqlite(dest_conn):
                    # SQLite does not support UPDATE ... JOIN
                    # Use correlated subquery + EXISTS
                    update_sql = f"""
                    UPDATE {dest_table_sql} AS d
                    SET {_quote_ident(dest_column)} = {ph}
                    WHERE EXISTS (
                        SELECT 1
                        FROM {src_table_sql} AS s
                        WHERE d.{_quote_ident("PERSON_ID")} = s.{_quote_ident("PERSON_ID")}
                          AND s.{_quote_ident(source_column)} = {ph}
                    );
                    """
                    dest_cursor.execute(update_sql, (translated_value, source_value))
                else:
                    update_sql = f"""
                    UPDATE {dest_table_sql} d
                    JOIN {src_table_sql} s ON d.{_quote_ident("PERSON_ID")} = s.{_quote_ident("PERSON_ID")}
                    SET d.{_quote_ident(dest_column)} = {ph}
                    WHERE s.{_quote_ident(source_column)} = {ph};
                    """
                    dest_cursor.execute(update_sql, (translated_value, source_value))

            # IMPORTANT: release write lock after each source table in SQLite
            if _is_sqlite(dest_conn):
                dest_conn.commit()

        # Final commit for non-SQLite / safety
        dest_conn.commit()