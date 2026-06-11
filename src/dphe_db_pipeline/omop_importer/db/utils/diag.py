"""Small SQLite diagnostics used while inspecting importer outputs."""

from __future__ import annotations

from typing import Any


def table_counts(cursor: Any, table_names: list[str]) -> dict[str, int | None]:
    """Return row counts for tables, using None when a table cannot be queried."""
    counts: dict[str, int | None] = {}
    for table_name in table_names:
        quoted_name = table_name.replace('"', '""')
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{quoted_name}"')
            counts[table_name] = int(cursor.fetchone()[0])
        except Exception:
            counts[table_name] = None
    return counts
