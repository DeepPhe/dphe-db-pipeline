# DeepPhe Input Format

This page describes the DeepPhe NLP output that Stage 1 loads and Stage 3 reads. It is the
contract your DeepPhe run must satisfy for the pipeline to produce useful results.

A complete, runnable example ships with the package at
`src/dphe_db_pipeline/resources/example/dphe_output/`.

## Directory layout

Stage 1 accepts three input shapes (see [Loader](../loader/README.md)):

```
dphe_output/                  # --input-dir
  fake_patient1/
    fake_patient1.json
    fake_patient1_Concepts.json
    fake_patient1_Cancers.json
    fake_patient1_26062026160543_D_1_Doc.json
    fake_patient1_26062026160543_D_2_Doc.json
    ...
  fake_patient2/
    ...
```

- `--input-dir DIR` — recursively scans the directory tree
- `--input-zip FILE` — a single zip archive containing the same tree
- `--input-zipdir DIR` — a directory tree of zip archives, one worker process per CPU

The per-patient subdirectory is a convention, not a requirement. Stage 1 stores every file
under its path relative to the input root, and Stage 3 identifies patients from the file
**basename** only — so a flat directory works too.

## File naming contract

This is the part that matters most. Stage 3 selects files from the Stage 1 database with
SQL `LIKE` patterns and derives the patient ID by stripping the suffix from the basename
(`src/dphe_db_pipeline/extractor/extractors/extract_cancers_data.py`):

| File | Selected by | Patient ID derived as |
|---|---|---|
| `<patient_id>_Cancers.json` | `filename LIKE '%_Cancers.json'` | basename minus `_Cancers.json` |
| `<patient_id>_Concepts.json` | `filename LIKE '%_Concepts.json'` and `filename NOT LIKE 'all_concepts_%'` | basename minus `_Concepts.json` |

Consequences worth knowing:

- **The `_Cancers.json` / `_Concepts.json` suffixes are mandatory.** A patient whose files
  are named differently is loaded into `files` but contributes nothing to extraction.
- **The patient ID must match across the two files**, and must match `PatientID` in the
  OMOP demographics source ([OMOP input format](omop-input.md)) for demographics to join.
- **Directory prefixes are ignored.** `p1/p1_Cancers.json` and `p1_Cancers.json` both yield
  patient ID `p1`, so basenames must be unique across the whole input tree.
- Aggregate files named `all_concepts_*` are explicitly excluded from concept extraction.
- `<patient_id>.json` and `*_Doc.json` files are **stored but not read by Stage 3**. They
  are preserved in the `files` table for downstream tools and full-text access.

## `<patient_id>.json` — patient record

Minimal patient identity record.

```json
{
  "id": "patient_X",
  "name": "patient_X"
}
```

## `<patient_id>_Concepts.json` — patient-level concepts

The primary input for concept extraction. Two top-level keys:

```json
{
  "concepts": [
    {
      "dpheGroup": "Behavior",
      "preferredText": "Invasive",
      "mentionIds": [
        "patient_X_26062026160551_M_91",
        "patient_X_26062026160551_M_154"
      ],
      "codifications": [
        { "source": "CUI", "codes": ["C0205281"] }
      ],
      "id": "patient_X_26062026160551_C_71",
      "classUri": "Invasive",
      "negated": false,
      "uncertain": false,
      "historic": false,
      "confidence": 87
    }
  ],
  "conceptRelations": [
    {
      "type": "hasAssociatedSite",
      "sourceId": "patient_X_26062026160551_C_45",
      "targetId": "patient_X_26062026160551_C_30"
    }
  ]
}
```

### `concepts[]` fields

| Field | Type | Used by | Notes |
|---|---|---|---|
| `dpheGroup` | string | Stage 3 | Semantic group; drives the patient-summary bucket. See [group values](#dphegroup-values). |
| `preferredText` | string | Stage 3 | Human-readable label, carried into `extracted_concepts` CSV. |
| `classUri` | string | Stage 3 | Ontology class; the grouping key in `concepts_by_group`. |
| `negated` | boolean | Stage 3 | Part of the grouping key. |
| `uncertain` | boolean | Stage 3 | Extracted to CSV; **not** part of the `concepts_by_group` key. |
| `historic` | boolean | Stage 3 | Extracted to CSV; **not** part of the `concepts_by_group` key. |
| `confidence` | integer | Stage 3 | 0–100; carried to CSV, not used for filtering. |
| `id` | string | — | Concept ID referenced by `conceptRelations` and `_Cancers.json`. |
| `mentionIds` | string[] | — | Links to `mentions[]` in the `_Doc.json` files. |
| `codifications` | object[] | — | `{source, codes[]}`, e.g. UMLS CUIs. |

`conceptRelations[]` is stored but not consumed by the extractor. Relation types seen in the
bundled example: `hasAssociatedSite`, `hasBehavior`, `hasClinical_T`/`_N`/`_M`,
`hasPathologic_T`/`_N`, `hasClockface`, `hasCourse`, `hasFinding`, `hasGene`, `hasGrade`,
`hasLaterality`, `hasLymphNode`, `hasMass`, `hasProcedure`, `hasQuadrant`, `hasStage`,
`hasTestResult`, `hasTissue`, `hasTreatment`.

### `dpheGroup` values

Groups map to patient-summary buckets in
`src/dphe_db_pipeline/extractor/patient_summaries/config.py`. Unmapped groups fall through to
the `other_concepts` bucket.

| Bucket | `dpheGroup` values |
|---|---|
| `diagnoses` | `Neoplasm`, `Disease or Disorder` |
| `staging` | `Disease Stage Qualifier`, `Generic TNM Finding`, `Pathologic TNM Finding` |
| `grading` | `Disease Grade Qualifier` |
| `biomarkers` | `Gene`, `Gene Product` |
| `findings` | `Clinical Test Result`, `Finding`, `Mass`, `Pathologic Process` |
| `procedures` | `Intervention or Procedure` |
| `treatments` | `Chemo/immuno/hormone Therapy Regimen`, `Pharmacologic Substance` |
| `behavior` | `Behavior` |
| `anatomy` | `Body Part`, `Lymph Node`, `Organ System`, `Tissue` |
| `clinical_course` | `Clinical Course of Disease` |
| `qualifiers` | `Disease Qualifier`, `General Qualifier`, `Side`, `Spatial Qualifier`, `Temporal Qualifier` |
| `other_concepts` | `Body Fluid or Substance`, `Dose`, `Property or Attribute`, anything unmapped |

## `<patient_id>_Cancers.json` — cancers, tumors, attributes

A **JSON array** (not an object) of cancer records. Each cancer contains tumors, and both
cancers and tumors carry attributes.

```json
[
  {
    "id": "patient_X_26062026160551_C_43_C",
    "classUri": "InvasiveBreastCarcinomaOfNoSpecialType",
    "negated": false,
    "uncertain": true,
    "historic": false,
    "confidence": 90,
    "conceptIds": ["patient_X_26062026160551_C_43"],
    "attributes": [
      {
        "name": "Location",
        "id": "patient_X_26062026160551_A_26",
        "values": [
          {
            "value": "Upper-Outer Quadrant of the Breast",
            "conceptIds": ["patient_X_26062026160551_C_26"],
            "id": "patient_X_26062026160551_AV_1",
            "classUri": "Upper_sub_OuterQuadrantOfTheBreast",
            "negated": false,
            "uncertain": false,
            "historic": true,
            "confidence": 96
          }
        ]
      }
    ],
    "tumors": [
      {
        "id": "patient_X_26062026160551_C_87_T",
        "classUri": "TumorMass",
        "negated": false,
        "uncertain": false,
        "historic": true,
        "confidence": 90,
        "conceptIds": ["patient_X_26062026160551_C_87"],
        "attributes": [ /* same shape as cancer-level attributes */ ]
      }
    ]
  }
]
```

Structure notes:

- Cancers and tumors share the same modifier fields: `classUri`, `negated`, `uncertain`,
  `historic`, `confidence`, `conceptIds`.
- `attributes[]` appears at **both** the cancer and tumor level. The extractor records which
  level each attribute came from in the `level` column of `extracted_attributes`.
- An attribute is `{name, id, values[]}`. The `name` (for example `Location`, `Laterality`,
  `Quadrant`, `Clockface`, `Topography, major`) becomes `attribute_name` in
  `attributes_by_group`.
- Each entry in `values[]` carries its own `classUri` and modifier flags. **The `value`
  string itself is deliberately ignored** by grouping — only `classUri` is used, because the
  same concept can surface under several free-text values.
- `conceptIds` reference `concepts[].id` in `_Concepts.json`.

## `<patient_id>_<timestamp>_D_<n>_Doc.json` — document records

One file per clinical document. Stored in the `files` table for downstream use; not read by
Stage 3 extraction.

```json
{
  "id": "patient_X_26062026160551_D_1",
  "name": "patientX_doc1_RAD",
  "type": "Radiology Report",
  "date": "201001211345",
  "episode": "Pre-diagnostic",
  "text": "===================================================================\r\nReport ID...",
  "mentions": [
    {
      "begin": 556,
      "end": 575,
      "id": "patient_X_26062026160551_M_6",
      "classUri": "DigitalMammography",
      "negated": false,
      "uncertain": false,
      "historic": false,
      "confidence": 100
    }
  ],
  "mentionRelations": [
    {
      "type": "hasAssociatedSite",
      "sourceId": "patient_X_26062026160551_M_3",
      "targetId": "patient_X_26062026160551_M_16"
    }
  ]
}
```

| Field | Notes |
|---|---|
| `date` | `YYYYMMDDHHMM`, e.g. `201001211345` |
| `episode` | e.g. `Pre-diagnostic` |
| `type` | e.g. `Radiology Report`, `Surgical Pathology Report`, `Clinical Note` |
| `text` | Full document text; `begin`/`end` in `mentions[]` are character offsets into it |
| `mentions[]` | Document-level spans; `id` values are referenced by `concepts[].mentionIds` |

Because `text` holds the full note, these files dominate database size. Stage 1 compresses
values with zstd by default.

## Requirements summary

**Required for a patient to appear in extraction output:**

- `<patient_id>_Cancers.json` — valid JSON array
- `<patient_id>_Concepts.json` — object with a `concepts` array

**Optional:**

- `<patient_id>.json`, `*_Doc.json` — stored, not extracted
- OMOP demographics for the same `patient_id` — without it the patient still appears, but
  its summary has empty demographics

## Malformed files

Stage 1 counts a file as an error if it cannot be read or stored; Stage 3 logs a warning and
skips any file whose content is not valid JSON.

By default the pipeline is strict — `--max-load-error-fraction` is `0.0`, so a single Stage 1
failure aborts the run. Raise it to tolerate a fraction of bad files:

```bash
uv run python -m dphe_db_pipeline.pipeline --input-dir ./my_dphe_output --max-load-error-fraction 0.1
```

## See also

- [Loader](../loader/README.md) — Stage 1 CLI, compression options, and the `files` table
- [OMOP input format](omop-input.md) — the demographics side of the contract
- [Output database](output-database.md) — what the extracted data turns into
