# OMOP Input Format

This page describes the demographics and diagnosis data that Stage 2 expects, for each of the
three source modes. For **how to configure and select** a mode, see
[Source modes](../importer/source-modes.md); this page covers **what the data must look like**.

Whichever mode you use, the join key back to Stage 1 is the patient identifier: it must match
the DeepPhe `<patient_id>` exactly (see [DeepPhe input format](deepphe-input.md)). Patients
present in only one side are silently dropped from the joined outputs.

## Mode comparison

| | `json` | `csv` | `mysql` |
|---|---|---|---|
| Input | One JSON file, or a directory of them | Directory of `.csv` files | Live MySQL database |
| Schema expected | `patients[]` array | OMOP-derived `*_VW` tables | Same `*_VW` tables |
| Table discovery | n/a | Filename becomes table name | `SHOW TABLES` |
| Writes source tables to SQLite | No | Yes | Yes |
| Produces `CALCULATED_PT_ICD_CODES` | No | Yes | Yes |
| Concept ID translation needed | No — plain values | Yes — OMOP concept IDs | Yes — OMOP concept IDs |

`json` is the simplest path and the one the bundled example uses. `csv` and `mysql` follow the
same config-driven pipeline and expect the same table shapes.

---

## `json` mode

### Shape

Validated against `src/dphe_db_pipeline/omop_importer/schemas/patient_demographics.schema.json`.

```json
{
  "patients": [
    {
      "PatientID": "fake_patient1",
      "PatientName": "Fake Patient One",
      "Race": "white",
      "Gender": "female",
      "Ethnicity": "Not Hispanic or Latino",
      "DateOfBirth": "04-01-1960",
      "CancerType": "BreastCancer",
      "AgeAtDiagnosis": 50,
      "AgeOfFirstEncounter": "48",
      "AgeOfLastEncounter": "54"
    }
  ]
}
```

`patients` is required. Within a patient, only `PatientID` is required — everything else is
optional and nullable. Unknown extra properties are permitted and ignored.

`JSON_SOURCE_PATH` may point at a single file **or** a directory, in which case every `.json`
file in it is read in filename order. A bare top-level array (no `patients` wrapper) is also
accepted, for compatibility with older packaged examples.

### Fields

| Field | Type | Destination | Notes |
|---|---|---|---|
| `PatientID` | string, non-empty | `CALCULATED_PATIENT_DATA.PERSON_ID`, `CALCULATED_DX_DATA.PERSON_ID` | **Required.** Must match the DeepPhe patient ID. |
| `Gender` | string \| null | `CALCULATED_PATIENT_DATA.GENDER` | Passed through as-is — no concept translation in this mode. |
| `Race` | string \| null | `CALCULATED_PATIENT_DATA.RACE` | Passed through as-is. |
| `Ethnicity` | string \| null | `CALCULATED_PATIENT_DATA.ETHNICITY` | Passed through as-is. |
| `DateOfBirth` | string \| null | `CALCULATED_PATIENT_DATA.DATE_OF_BIRTH` | `MM-DD-YYYY` in, `YYYY-MM-DD` out. |
| `CancerType` | string \| null | `CALCULATED_DX_DATA.CANCER` | Normalized to a single letter. |
| `AgeAtDiagnosis` | number \| string \| null | `CALCULATED_DX_DATA.AGE_AT_DX` | Integer age. |
| `PatientName` | string \| null | — | Accepted by the schema; not written to calculated tables. |
| `AgeOfFirstEncounter` | string \| null | — | Accepted by the schema; not written to calculated tables. |
| `AgeOfLastEncounter` | string \| null | — | Accepted by the schema; not written to calculated tables. |

Because `Gender`/`Race`/`Ethnicity` are passed through verbatim, whatever strings you supply
are what appear in the `omop_gender` / `omop_race` / `omop_ethnicity` facet tables and in
patient summaries. Pick consistent values.

JSON mode has no ICD data to work from, so `CALCULATED_DX_DATA.CODE`, `.VOCAB`, and `.DATE`
are left `NULL` and `CALCULATED_PT_ICD_CODES` is not built at all.

### Normalization rules

- `DateOfBirth`: `MM-DD-YYYY` → `YYYY-MM-DD`. ISO `YYYY-MM-DD` is also accepted. Blank,
  unparseable, or one of `unknown` / `unk` / `na` / `n/a` / `none` / `null` → `NULL`.
- `CancerType`: `BreastCancer` → `B`, `OvarianCancer` → `O`, `Melanoma` → `M`. Matching
  ignores case, spaces, hyphens, and underscores, so `breast cancer` and `Breast_Cancer` also
  work, and a bare `B` / `O` / `M` is accepted. Anything else → `NULL`.
- `AgeAtDiagnosis`: numbers and numeric strings are truncated to an integer. Negative values
  and the unknown markers above → `NULL`.
- Missing or blank `PatientID` → record skipped.
- Duplicate `PatientID` → the existing row is updated (last write wins), across files too.

The bundled example lives at
`src/dphe_db_pipeline/resources/example/omop_data/patient_demographics.json`.

---

## `csv` mode

### How files map to tables

Every `.csv` file in `SOURCE_DIR` is imported. The table name is the **filename without its
extension**, and every column is created as `TEXT` from the header row. The table is dropped
and recreated on each run.

```
source_csvs/
  DEMOGRAPHIC_BRCAOVCA_VW.csv     ->  table DEMOGRAPHIC_BRCAOVCA_VW
  DIAGNOSIS_BRCAOVCA_HOSP_VW.csv  ->  table DIAGNOSIS_BRCAOVCA_HOSP_VW
```

Files must have a header row. Extra CSVs beyond the tables below are imported without error
but do not contribute to any calculated output.

### Tables and columns the pipeline actually reads

Derived from `src/dphe_db_pipeline/omop_importer/omop-config.js`. A missing table or column
does not crash the run — it produces empty or partial calculated tables, which is the usual
cause of "the importer ran but my data isn't there".

#### Demographics

`DEMOGRAPHIC_BRCAOVCA_VW` and `DEMOGRAPHIC_MELANOMA_VW`

| Column | Feeds |
|---|---|
| `PERSON_ID` | `CALCULATED_PATIENT_DATA.PERSON_ID` (also the join key) |
| `YEAR_OF_BIRTH` | `CALCULATED_PATIENT_DATA.DATE_OF_BIRTH` |
| `MONTH_OF_BIRTH` | `CALCULATED_PATIENT_DATA.DATE_OF_BIRTH` |
| `DAY_OF_BIRTH` | `CALCULATED_PATIENT_DATA.DATE_OF_BIRTH` |
| `GENDER_CONCEPT_ID` | `CALCULATED_PATIENT_DATA.GENDER`, via concept translation |
| `RACE_CONCEPT_ID` | `CALCULATED_PATIENT_DATA.RACE`, via concept translation |
| `ETHNICITY_CONCEPT_ID` | `CALCULATED_PATIENT_DATA.ETHNICITY`, via concept translation |

The three birth columns are combined into a single `DATE_OF_BIRTH` date.

#### Diagnoses

`DIAGNOSIS_BRCAOVCA_HOSP_VW`, `DIAGNOSIS_BRCAOVCA_OUTPT_VW`,
`DIAGNOSIS_MELANOMA_HOSP_VW`, `DIAGNOSIS_MELANOMA_OUTPT_VW`

| Column | Feeds |
|---|---|
| `PERSON_ID` | `CALCULATED_PT_ICD_CODES.PERSON_ID` |
| `CONDITION_SOURCE_VALUE` | The ICD code matched against the `ICD_CODES` lookup |
| `CONDITION_START_DATE` | `CALCULATED_PT_ICD_CODES.DATE`, expected as `YYYY-MM-DD` |
| `CONDITION_CONCEPT_ID` | Typed/indexed by the config; not used in the ICD derivation |

All four tables are scanned together. `CONDITION_SOURCE_VALUE` is matched by prefix against
the ICD lookup to derive the `CANCER` letter.

#### Death

`DEATH_BRCAOVCA_VW` and `DEATH_MELANOMA_VW`

| Column | Notes |
|---|---|
| `PERSON_ID` | Indexed |
| `DEATH_DATE` | Cast to `DATE` |

These are typed and indexed by the config but are not currently consumed by any calculated
table.

### OMOP concept ID translation

In `csv` and `mysql` mode, demographics arrive as OMOP concept IDs and are translated to
readable values by `src/dphe_db_pipeline/omop_importer/omop_mappers/demographics.py`.
**Unrecognized IDs do not error — they fall back to a default**, which is a common source of
surprising "everything is Unknown" output.

Gender:

| Concept ID | Value |
|---|---|
| `8507` | `M` |
| `8532` | `F` |
| `8551` | `U` |
| anything else | `U` |

Race (20 mappings), a selection:

| Concept ID | Value |
|---|---|
| `8527` | White |
| `8515` | Asian |
| `8557` | Native Hawaiian or Other Pacific Islander |
| `8657` | American Indian or Alaska Native |
| `38003598` | Black |
| anything else | `Unknown` |

Ethnicity uses the same pattern with an `Unknown` fallback. See the mapper module for the
complete race list.

### ICD lookup table

`ICD_CODES` is built from `src/dphe_db_pipeline/omop_importer/lookup_tables/ICD_CODES/icd.bsv`,
a **pipe-delimited** file:

```
CODE|VOCAB|CANCER
C50.0|ICD10|B
C50.1|ICD10|B
```

| Column | Meaning |
|---|---|
| `CODE` | ICD-9-CM or ICD-10-CM code prefix |
| `VOCAB` | `ICD9` or `ICD10` |
| `CANCER` | `B` (breast), `O` (ovarian), `M` (melanoma) |

This is a curated 52-row subset covering breast, ovarian, and melanoma, not a complete ICD
code set. Codes outside it do not map to a cancer letter. Add rows here to extend coverage.

---

## `mysql` mode

Same expected schema as `csv` mode. The difference is discovery and transport:

- The importer connects with the `MYSQL_*` settings and runs `SHOW TABLES`
- **Every** table found is copied — `SELECT *`, streamed in 5,000-row batches
- Each is recreated in SQLite with all columns as `TEXT`, dropping any existing table
- MySQL is strictly read-only; the connection needs only `SELECT` privileges
- The rest of the pipeline runs entirely against SQLite

Because discovery is "everything in the database", point `MYSQL_DATABASE` at a schema that
contains the `*_VW` tables above. Extra tables are copied harmlessly but ignored.

## Verifying what was imported

```bash
sqlite3 output/databases/individual/omop.sqlite3 ".tables"
sqlite3 output/databases/individual/omop.sqlite3 "SELECT COUNT(*) FROM CALCULATED_PATIENT_DATA;"
sqlite3 output/databases/individual/omop.sqlite3 "SELECT * FROM CALCULATED_PATIENT_DATA LIMIT 5;"
```

If you see many `*_VW` tables you ran `csv` or `mysql`; if you see only `CALCULATED_*` tables
you ran `json`.

## See also

- [Source modes](../importer/source-modes.md) — environment variables and CLI flags per mode
- [Table catalog](../importer/table-catalog.md) — the tables Stage 2 writes to `omop.sqlite3`
- [Config reference](../importer/config-reference.md) — how to change the expected schema
- [Troubleshooting](../importer/troubleshooting.md) — common import failures
- [Output database](output-database.md) — how this data reaches the final database
