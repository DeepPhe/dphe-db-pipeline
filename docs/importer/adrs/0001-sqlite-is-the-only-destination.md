# ADR 0001: SQLite is the only destination

## Status

Accepted

## Context

Earlier iterations of the project mixed MySQL and SQLite concerns more heavily. That made the write path harder to reason about and increased the amount of mode-specific branching.

## Decision

All writes go to a single SQLite destination database defined by `SQLITE_DB_PATH`.

## Consequences

Positive:
- one consistent destination model
- easier local runs and scratch databases
- easier verification with `sqlite3`
- fewer cross-database write branches

Tradeoffs:
- some legacy naming/config still reflects earlier schema-oriented behavior
- compatibility helpers are still needed in a few places where config is MySQL-shaped

