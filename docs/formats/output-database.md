# Output Database Structure

The pipeline's primary deliverable is `deepphe.sqlite3` — a single SQLite file containing the
raw DeepPhe files, patient-grouped concept indexes, demographic facets, and per-patient
summaries. This page documents every table in it.

Default location: `output/databases/individual/deepphe.sqlite3` (override with
`--compressed-db`).

`omop.sqlite3` is a separate, intermediate database written by Stage 2; see
[Table catalog](../importer/table-catalog.md) for its schema.

## Table overview

| Table | Written by | Rows | Purpose |
|---|---|---|---|
| `files` | Stage 1 | one per input file | Raw DeepPhe output, optionally compressed |
| `patient_id_mapping` | Stage 3 | one per patient | `patient_id` ↔ `sequential_id`; the join key for every bitmap |
| `concepts_by_group` | Stage 3 | one per (group, class, negated) | Concept index with patient bitmaps |
| `attributes_by_group` | Stage 3 | one per (name, class, modifiers) | Cancer/tumor attribute index |
| `cancers_by_group` | Stage 3 | one per (class, modifiers) | Cancer index |
| `tumors_by_group` | Stage 3 | one per (class, modifiers) | Tumor index |
| `omop_gender` | Stage 3 | one per distinct value | Demographic facet |
| `omop_race` | Stage 3 | one per distinct value | Demographic facet |
| `omop_ethnicity` | Stage 3 | one per distinct value | Demographic facet |
| `omop_cancers` | Stage 3 | one per distinct value | Cancer-type facet |
| `omop_age_at_dx` | Stage 3 | one per distinct value | Age-at-diagnosis facet |
| `patient_summaries` | Stage 3 | one per patient | zstd-compressed JSON summary |

Everything except `files` is dropped and rebuilt on each Stage 3 run.

## `files` — raw DeepPhe output

```sql
CREATE TABLE files (
    filename TEXT PRIMARY KEY,
    content  BLOB NOT NULL,
    encoding TEXT NOT NULL DEFAULT 'raw'
);
CREATE INDEX idx_files_filename ON files(filename);
```

| Column | Notes |
|---|---|
| `filename` | Path relative to the Stage 1 input root, e.g. `fake_patient1/fake_patient1_Cancers.json` |
| `content` | File bytes, compressed per `encoding` |
| `encoding` | `zstd` (default), `lz4`, or `raw` |

Writing the same `filename` twice overwrites the row (`INSERT OR REPLACE`). A single database
typically mixes encodings, because values below `--min-compress-bytes` (default 512) are
stored raw.

Decoding a value:

```python
import sqlite3, zstandard as zstd

conn = sqlite3.connect("output/databases/individual/deepphe.sqlite3")
content, encoding = conn.execute(
    "SELECT content, encoding FROM files WHERE filename = ?",
    ("fake_patient1/fake_patient1_Cancers.json",),
).fetchone()

if encoding == "zstd":
    text = zstd.ZstdDecompressor().decompress(content).decode("utf-8")
else:
    text = content.decode("utf-8")
```

The helper `dphe_db_pipeline.extractor.stored_content.decode_stored_content(content, encoding)`
does this for all three encodings.

## `patient_id_mapping` — the join key

```sql
CREATE TABLE patient_id_mapping (
    sequential_id INTEGER PRIMARY KEY,
    patient_id    TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_patient_id ON patient_id_mapping(patient_id);
```

Sequential IDs are assigned from `0` in first-seen order during Stage 3. **Every
`patient_bitmap` in this database and every `patient_summaries.patient_id` refers to
`sequential_id`, not to the original string ID.** IDs are not stable across runs — treat them
as valid only within one database file.

## The `*_by_group` tables

All four share the same design: one row per distinct combination of concept identity and
modifier flags, holding the set of patients that match, encoded as a **serialized
[Roaring bitmap](https://roaringbitmap.org/)** over `sequential_id`.

This makes the database small and set operations fast: intersecting two concepts is a bitmap
AND, not a join.

### `concepts_by_group`

```sql
CREATE TABLE concepts_by_group (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dpheGroup      TEXT NOT NULL,
    classUri       TEXT NOT NULL,
    negated        BOOLEAN NOT NULL,
    num_patients   INTEGER NOT NULL,
    patient_bitmap BLOB NOT NULL
);
CREATE INDEX idx_concepts_dpheGroup ON concepts_by_group(dpheGroup);
CREATE INDEX idx_concepts_classUri  ON concepts_by_group(classUri);
CREATE INDEX idx_concepts_negated   ON concepts_by_group(negated);
```

Grouping key is `(dpheGroup, classUri, negated)`. Note that `uncertain` and `historic` are
**not** part of the key here — unlike the other three tables — so a concept appears at most
twice per group, once negated and once not.

Example rows:

| dpheGroup | classUri | negated | num_patients |
|---|---|---|---|
| Behavior | Benign | 0 | 18 |
| Behavior | Benign | 1 | 4 |
| Behavior | InSitu | 0 | 68 |

### `attributes_by_group`

```sql
CREATE TABLE attributes_by_group (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    attribute_name TEXT NOT NULL,
    classUri       TEXT NOT NULL,
    negated        BOOLEAN NOT NULL,
    uncertain      BOOLEAN NOT NULL,
    historic       BOOLEAN NOT NULL,
    num_patients   INTEGER NOT NULL,
    patient_bitmap BLOB NOT NULL
);
CREATE INDEX idx_attributes_name      ON attributes_by_group(attribute_name);
CREATE INDEX idx_attributes_classUri  ON attributes_by_group(classUri);
CREATE INDEX idx_attributes_modifiers ON attributes_by_group(negated, uncertain, historic);
```

Grouping key is `(attribute_name, classUri, negated, uncertain, historic)`. `attribute_name`
comes from the attribute's `name` in `_Cancers.json`; `classUri` comes from the attribute
**value**. The free-text `value` string is intentionally not part of the key.

Attributes from both the cancer level and the tumor level land in this one table.

### `cancers_by_group` and `tumors_by_group`

```sql
CREATE TABLE cancers_by_group (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    classUri       TEXT NOT NULL,
    negated        BOOLEAN NOT NULL,
    uncertain      BOOLEAN NOT NULL,
    historic       BOOLEAN NOT NULL,
    num_patients   INTEGER NOT NULL,
    patient_bitmap BLOB NOT NULL
);
```

`tumors_by_group` is identical in shape. Grouping key is
`(classUri, negated, uncertain, historic)`.

### Reading a bitmap

```python
import sqlite3
from pyroaring import BitMap

conn = sqlite3.connect("output/databases/individual/deepphe.sqlite3")

class_uri, blob = conn.execute(
    "SELECT classUri, patient_bitmap FROM cancers_by_group "
    "WHERE classUri = ? AND negated = 0 AND uncertain = 0 AND historic = 0",
    ("InvasiveBreastCarcinomaOfNoSpecialType",),
).fetchone()

sequential_ids = BitMap.deserialize(blob)

# Back to original patient IDs
placeholders = ",".join("?" * len(sequential_ids))
rows = conn.execute(
    f"SELECT patient_id FROM patient_id_mapping WHERE sequential_id IN ({placeholders})",
    list(sequential_ids),
).fetchall()
```

Intersecting two indexes — patients with both a given cancer and a given biomarker:

```python
both = BitMap.deserialize(cancer_blob) & BitMap.deserialize(biomarker_blob)
```

`num_patients` is always `len(bitmap)`, denormalized so counts can be read without
deserializing.

:::note
If `pyroaring` is unavailable when Stage 3 runs, bitmaps are written as empty blobs and
`num_patients` still reflects the real count. An all-empty `patient_bitmap` column means the
dependency was missing during the build.
:::

## The `omop_*` facet tables

Five tables of the same shape, built by joining Stage 2's `CALCULATED_PATIENT_DATA` and
`CALCULATED_DX_DATA` against `patient_id_mapping`:

```sql
CREATE TABLE omop_gender (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    gender         TEXT NOT NULL,
    num_patients   INTEGER NOT NULL,
    patient_bitmap BLOB NOT NULL
);
CREATE INDEX idx_omop_gender_gender ON omop_gender(gender);
```

| Table | Value column | Source |
|---|---|---|
| `omop_gender` | `gender` | `CALCULATED_PATIENT_DATA.GENDER` |
| `omop_race` | `race` | `CALCULATED_PATIENT_DATA.RACE` |
| `omop_ethnicity` | `ethnicity` | `CALCULATED_PATIENT_DATA.ETHNICITY` |
| `omop_cancers` | `cancer` | `CALCULATED_DX_DATA.CANCER` |
| `omop_age_at_dx` | `age_at_dx` | `CALCULATED_DX_DATA.AGE_AT_DX` |

Behavior worth knowing:

- Values are stored as **text**, including `age_at_dx`. Rows in `omop_age_at_dx` are sorted
  numerically where possible, others alphabetically.
- `NULL` or blank gender/race/ethnicity becomes the literal string `Unknown`. Blank
  `AGE_AT_DX` and `CANCER` values are skipped rather than bucketed.
- Patients present in OMOP but absent from `patient_id_mapping` are skipped, and vice versa.
- If `omop.sqlite3` is missing `CALCULATED_PATIENT_DATA` or `CALCULATED_DX_DATA`, Stage 3
  logs a warning and **skips creating the `omop_*` tables entirely** rather than failing.
  Patient summaries then have empty demographics.

## `patient_summaries` — per-patient rollup

```sql
CREATE TABLE patient_summaries (
    patient_id   INTEGER PRIMARY KEY,
    summary_json BLOB NOT NULL
);
CREATE INDEX idx_patient_summaries_patient_id ON patient_summaries(patient_id);
```

Despite the column name, `patient_id` here is the **`sequential_id`** from
`patient_id_mapping`. `summary_json` is a zstd-compressed UTF-8 JSON object.

```python
import sqlite3, json, zstandard as zstd

conn = sqlite3.connect("output/databases/individual/deepphe.sqlite3")
blob, = conn.execute(
    "SELECT summary_json FROM patient_summaries WHERE patient_id = 0"
).fetchone()
summary = json.loads(zstd.ZstdDecompressor().decompress(blob))
```

### Summary JSON shape

```json
{
  "patient_id": "fake_patient101",
  "sequential_id": 0,
  "demographics": {
    "age_at_dx": "72",
    "gender": "female",
    "race": "white",
    "ethnicity": "Unknown",
    "cancer_type": "B"
  },
  "diagnoses": [
    { "name": "Skin Scar" },
    { "name": "Invasive Breast Lobular Carcinoma", "historic": true },
    { "name": "Metastatic Lesion", "negated": true }
  ],
  "staging": [{ "name": "Stage I" }, { "name": "M0" }, { "name": "N0" }],
  "grading": [{ "name": "Grade 2" }],
  "biomarkers": [
    { "name": "ESR1 Gene" },
    { "name": "ERBB2 Gene", "conflicted": true }
  ]
}
```

Buckets, in emission order: `diagnoses`, `staging`, `grading`, `biomarkers`, `procedures`,
`treatments`, `findings`, `behavior`, `anatomy`, `clinical_course`, `qualifiers`, `cancers`,
`tumors`, `other_concepts`.

- **Empty buckets are omitted** from the object entirely — do not assume every key is present.
- Each entry is `{"name": <humanized classUri>}`. The flags `negated`, `uncertain`,
  `historic`, and `conflicted` are included **only when true**, never as `false`.
- `conflicted: true` marks a name that appeared **both affirmed and negated** within the same
  bucket. The affirmed entry wins, its `negated` key is dropped, and `conflicted` is set.
- Names are humanized from `classUri` — `InvasiveBreastCarcinomaOfNoSpecialType` becomes
  `Invasive Breast Carcinoma Of No Special Type`. The raw URI is not carried into the summary;
  use the `*_by_group` tables when you need it.
- Setting `SLIM_MODE = True` in
  `src/dphe_db_pipeline/extractor/patient_summaries/config.py` suppresses the `qualifiers`,
  `anatomy`, `clinical_course`, and `other_concepts` buckets.

## Intermediate files

Stage 3 also writes plain-text intermediates to `output/extraction/data/` (override with
`--output-dir`). These are inputs to the database tables above, useful for debugging or
external analysis.

Sharded per-record CSVs:

| File | Columns |
|---|---|
| `extracted_concepts/extracted_concepts_*.csv` | `patient_id, dpheGroup, preferredText, classUri, negated, uncertain, historic, confidence` |
| `extracted_cancers/extracted_cancers_*.csv` | `patient_id, cancer_index, cancer_id, classUri, negated, uncertain, historic, confidence` |
| `extracted_tumors/extracted_tumors_*.csv` | `patient_id, cancer_index, tumor_index, tumor_id, classUri, conceptIds, negated, uncertain, historic, confidence` |
| `extracted_attributes/extracted_attributes_*.csv` | `patient_id, cancer_index, tumor_index, level, attribute_name, attribute_id, classUri, value_id, negated, uncertain, historic, confidence` |

Grouped CSVs, which map one-to-one onto the `*_by_group` tables (with `patient_ids` as a
comma-separated list instead of a bitmap):

| File | Columns |
|---|---|
| `concepts_by_group.csv` | `dpheGroup, classUri, negated, num_patients, patient_ids` |
| `attributes_by_group.csv` | `attribute_name, classUri, negated, uncertain, historic, num_patients, patient_ids` |
| `cancers_by_group.csv` | `classUri, negated, uncertain, historic, num_patients, patient_ids` |
| `tumors_by_group.csv` | `classUri, negated, uncertain, historic, num_patients, patient_ids` |

Plus `patient_summaries.jsonl` — one uncompressed summary JSON object per line, the direct
source of the `patient_summaries` table.

`concepts_by_group.csv`, `cancers_by_group.csv`, and `tumors_by_group.csv` are required;
Stage 3 fails if they are not produced. `attributes_by_group.csv` is optional.

## Inspecting a database

```bash
sqlite3 output/databases/individual/deepphe.sqlite3 ".tables"
sqlite3 output/databases/individual/deepphe.sqlite3 "SELECT COUNT(*) FROM patient_id_mapping;"
sqlite3 output/databases/individual/deepphe.sqlite3 \
  "SELECT dpheGroup, classUri, num_patients FROM concepts_by_group ORDER BY num_patients DESC LIMIT 10;"
```

A healthy full run has all twelve tables populated. Common shortfalls:

| Symptom | Cause |
|---|---|
| Only `files` exists | Stage 3 did not run, or ran against a different database path |
| `*_by_group` tables empty | No files matched `%_Cancers.json` / `%_Concepts.json` — see [DeepPhe input format](deepphe-input.md) |
| `omop_*` tables missing | `omop.sqlite3` lacked the `CALCULATED_*` tables |
| `omop_*` present but all `Unknown` | Patient IDs did not join, or concept IDs were unrecognized — see [OMOP input format](omop-input.md) |
| Summaries with empty demographics | Same as above; the join key is the patient ID string |

## See also

- [DeepPhe input format](deepphe-input.md) — what feeds the extraction tables
- [OMOP input format](omop-input.md) — what feeds the `omop_*` facets
- [Table catalog](../importer/table-catalog.md) — the intermediate `omop.sqlite3` schema
- [Loader API reference](../loader/API_REFERENCE.md) — programmatic access to the `files` table
