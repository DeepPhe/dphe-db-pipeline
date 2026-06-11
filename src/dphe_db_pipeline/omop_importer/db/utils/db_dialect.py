import sqlite3
from collections.abc import Iterable
from typing import Any


def is_sqlite_connection(conn: Any) -> bool:
    """
    Return True if the DB connection is a sqlite3 connection.
    """
    return isinstance(conn, sqlite3.Connection)


def db_flavor(conn: Any) -> str:
    """
    Return 'sqlite' or 'mysql' based on the connection object type.
    """
    return "sqlite" if is_sqlite_connection(conn) else "mysql"


def placeholder(conn: Any) -> str:
    """
    Parameter placeholder for the current DB driver.
    sqlite3 -> '?'
    mysql-connector / pymysql -> '%s'
    """
    return "?" if is_sqlite_connection(conn) else "%s"


def placeholders(conn: Any, n: int) -> str:
    """
    Comma-separated placeholders, e.g. '?, ?, ?' or '%s, %s, %s'
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    p = placeholder(conn)
    return ", ".join([p] * n)


def quote_ident(name: str) -> str:
    """
    Safely quote a SQL identifier with backticks.
    Supports dotted identifiers like schema.table -> `schema`.`table`
    """
    if name is None:
        raise ValueError("Identifier cannot be None")

    name = str(name).strip()
    if not name:
        raise ValueError("Identifier cannot be empty")

    parts = [part.strip() for part in name.split(".")]
    quoted_parts = []
    for part in parts:
        if not part:
            raise ValueError(f"Invalid identifier: {name!r}")
        # Escape backticks inside identifiers
        part = part.replace("`", "``")
        quoted_parts.append(f"`{part}`")
    return ".".join(quoted_parts)


def table_ref(table_name: str) -> str:
    """
    Alias for quote_ident for readability.
    """
    return quote_ident(table_name)


def column_ref(column_name: str) -> str:
    """
    Alias for quote_ident for readability.
    """
    return quote_ident(column_name)


def sqlite_pragma_index_list(cursor: Any, table_name: str):
    """
    Returns rows from PRAGMA index_list(table_name).
    """
    # PRAGMA table/index names should be bare names (no schema dot here in most sqlite usage).
    bare_name = str(table_name).split(".")[-1].strip().replace("`", "")
    cursor.execute(f"PRAGMA index_list({quote_ident(bare_name)});")
    return cursor.fetchall()


def normalize_rowcount(cursor: Any) -> int:
    """
    sqlite3 often reports -1 for SELECT rowcount. Preserve behavior but normalize None.
    """
    rc = getattr(cursor, "rowcount", None)
    return -1 if rc is None else rc


def fetchall_if_available(cursor: Any) -> Iterable | None:
    """
    Utility if you want to inspect rows after a SELECT.
    Not used by all callers, but handy for diagnostics.
    """
    try:
        return cursor.fetchall()
    except Exception:
        return None
