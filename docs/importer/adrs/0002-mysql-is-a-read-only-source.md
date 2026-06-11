# ADR 0002: MySQL is a read-only source

## Status

Accepted

## Context

The project still needs to ingest data from existing MySQL-hosted OMOP datasets, but maintaining MySQL write behavior complicates the system and is no longer required.

## Decision

When `SOURCE_TYPE=mysql`, the importer may only read from MySQL.

The code:
- discovers tables with `SHOW TABLES`
- inspects columns with `SELECT * FROM table LIMIT 0`
- streams rows with `SELECT * FROM table`
- recreates the data in SQLite

## Consequences

Positive:
- reduced operational risk
- lower permission requirements (`SELECT` only)
- clearer architecture

Tradeoffs:
- importing from MySQL adds a copy step before downstream processing
- debugging source data still sometimes requires looking at the MySQL origin directly
