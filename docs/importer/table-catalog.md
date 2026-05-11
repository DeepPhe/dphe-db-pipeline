# Table Catalog

This document groups the major tables by role.

## 1. Imported source tables

These are copied into SQLite from CSV or MySQL sources. They do **not** exist in JSON-only runs.

Representative examples:
- `DEMOGRAPHIC_BRCAOVCA_VW`
- `DEMOGRAPHIC_MELANOMA_VW`
- `DIAGNOSIS_BRCAOVCA_HOSP_VW`
- `DIAGNOSIS_BRCAOVCA_OUTPT_VW`
- `DIAGNOSIS_MELANOMA_HOSP_VW`
- `DIAGNOSIS_MELANOMA_OUTPT_VW`
- `DEATH_BRCAOVCA_VW`
- `DEATH_MELANOMA_VW`

These tables are the input to much of the config-driven transformation pipeline.

## 2. Lookup tables

### `ICD_CODES`

Purpose:
- reference lookup for ICD-based cancer mappings

Typical columns:
- `CODE`
- `DESCRIPTION`
- `CANCER`
- `VOCAB`

### `SNOMED_CODES`

Purpose:
- reference lookup for SNOMED-based cancer mappings

Typical columns:
- `CODE`
- `CODE_DEFINITION`
- `PREFERRED_TERM`
- `VOCAB`
- `CANCER`

## 3. Calculated tables

### `CALCULATED_PATIENT_DATA`

Purpose:
- consolidated patient-level demographic output

Typical columns:
- `PERSON_ID`
- `GENDER`
- `RACE`
- `ETHNICITY`
- `DATE_OF_BIRTH`

Exists in:
- `csv`
- `mysql`
- `json`

### `CALCULATED_DX_DATA`

Purpose:
- patient-level diagnosis/cancer summary output

Typical columns:
- `PERSON_ID`
- `CODE`
- `VOCAB`
- `DATE`
- `CANCER`
- `AGE_AT_DX`

Exists in:
- `csv`
- `mysql`
- `json`

### `CALCULATED_PT_ICD_CODES`

Purpose:
- derived patient-to-ICD mapping table used in the source-table-driven pipeline

Typical columns:
- `PERSON_ID`
- `VOCAB`
- `PARENT`
- `DATE`
- `CANCER`

Exists in:
- `csv`
- `mysql`
- not currently expected in JSON-only mode

## Expectations by mode

| Table group | CSV | MySQL | JSON |
|---|---|---|---|
| Imported source tables | Yes | Yes | No |
| Lookup tables | Yes | Yes | Limited / mode-dependent |
| `CALCULATED_PATIENT_DATA` | Yes | Yes | Yes |
| `CALCULATED_DX_DATA` | Yes | Yes | Yes |
| `CALCULATED_PT_ICD_CODES` | Yes | Yes | No |

## Good sanity checks

If you are unsure which path ran, inspect the destination database:

- If you see many imported `*_VW` tables, you likely ran `csv` or `mysql`.
- If you only see calculated tables after a clean run, you likely ran `json`.

