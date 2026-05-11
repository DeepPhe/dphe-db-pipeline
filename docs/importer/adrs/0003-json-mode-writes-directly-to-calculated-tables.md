# ADR 0003: JSON mode writes directly to calculated tables

## Status

Accepted

## Context

The JSON input currently represents patient-level demographics/diagnosis summary data, not the full source-table shape used by CSV and MySQL ingestion.

## Decision

`SOURCE_TYPE=json` writes directly to `CALCULATED_PATIENT_DATA` and `CALCULATED_DX_DATA` instead of attempting to reconstruct the full source-table pipeline.

## Consequences

Positive:
- simple and fast JSON test runs
- clear contract for patient-level ingestion
- fewer assumptions about missing source-table detail

Tradeoffs:
- JSON mode is not feature-equivalent to `csv`/`mysql`
- source-table-dependent translations and ICD extraction are skipped
- documentation must be explicit so users do not assume full parity

