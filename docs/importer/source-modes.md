# Source Modes

This project supports three ingestion modes controlled by `SOURCE_TYPE`.

## Mode summary

| Mode | Purpose | Required settings | Result |
|---|---|---|---|
| `csv` | Import source tables from flat files | `SOURCE_DIR`, `SQLITE_DB_PATH` | Source tables + lookup tables + calculated tables |
| `mysql` | Copy source tables from MySQL into SQLite | `MYSQL_*`, `SQLITE_DB_PATH` | Source tables + lookup tables + calculated tables |
| `json` | Import demographics directly to calculated tables | `JSON_SOURCE_PATH`, `SQLITE_DB_PATH` | Calculated tables only |

## `csv`

### When to use it

Use this when you have a directory of source CSV files that correspond to expected OMAP source table names.

### Required settings

```dotenv
SOURCE_TYPE=csv
SOURCE_DIR=/path/to/csvs
SQLITE_DB_PATH=output/databases/deepphe.sqlite3
```

### What happens

- All CSV files in `SOURCE_DIR` are loaded into SQLite
- The config-driven pipeline runs against those imported source tables
- Calculated tables and lookup tables are rebuilt

### Expected tables

- Imported source tables (many)
- `ICD_CODES`
- `SNOMED_CODES`
- `CALCULATED_PATIENT_DATA`
- `CALCULATED_DX_DATA`
- `CALCULATED_PT_ICD_CODES`

## `mysql`

### When to use it

Use this when source data already exists in MySQL and you want to read it without writing anything back.

### Required settings

```dotenv
SOURCE_TYPE=mysql
SQLITE_DB_PATH=output/databases/deepphe.sqlite3
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=youruser
MYSQL_PASSWORD=yourpassword
MYSQL_DATABASE=omap
```

### What happens

- The importer connects to MySQL
- It discovers source tables with `SHOW TABLES`
- It reads each table using `SELECT`
- It recreates those tables in SQLite
- The rest of the pipeline runs entirely in SQLite

### Notes

- MySQL is read-only
- The MySQL user only needs `SELECT` privileges

## `json`

### When to use it

Use this when you have a patient demographics JSON file and you only need patient- and diagnosis-level calculated outputs.

### Required settings

```dotenv
SOURCE_TYPE=json
JSON_SOURCE_PATH=/path/to/patient_demographics.json
SQLITE_DB_PATH=output/databases/deepphe.sqlite3
```

### What happens

- JSON payloads are read from a single file or a directory of JSON files
- The importer normalizes and upserts patient-level data into calculated tables
- Source-table-dependent pipeline steps are skipped

### JSON shape

```json
{
  "patients": [
    {
      "PatientID": "fake_patient1",
      "Race": "white",
      "Gender": "female",
      "DateOfBirth": "04-01-1960",
      "CancerType": "BreastCancer",
      "AgeAtDiagnosis": 50
    }
  ]
}
```

### JSON field mapping

| JSON field | Destination table | Destination column |
|---|---|---|
| `PatientID` | `CALCULATED_PATIENT_DATA` | `PERSON_ID` |
| `Gender` | `CALCULATED_PATIENT_DATA` | `GENDER` |
| `Race` | `CALCULATED_PATIENT_DATA` | `RACE` |
| `Ethnicity` | `CALCULATED_PATIENT_DATA` | `ETHNICITY` |
| `DateOfBirth` | `CALCULATED_PATIENT_DATA` | `DATE_OF_BIRTH` |
| `PatientID` | `CALCULATED_DX_DATA` | `PERSON_ID` |
| `CancerType` | `CALCULATED_DX_DATA` | `CANCER` |
| `AgeAtDiagnosis` | `CALCULATED_DX_DATA` | `AGE_AT_DX` |

### Normalization rules

- `DateOfBirth`: `MM-DD-YYYY` -> `YYYY-MM-DD`
- unknown/blank/invalid dates -> `NULL`
- `CancerType`: `BreastCancer` -> `B`, `OvarianCancer` -> `O`, `Melanoma` -> `M`
- unrecognized cancers -> `NULL`
- missing `PatientID` -> skip record
- duplicate `PatientID` -> update the existing patient row

### Important limitation

JSON mode is **not** full parity with `csv`/`mysql` mode. It does not build the same source-table-based derived outputs.

