# Config Reference

`omop-config.js` is the main pipeline contract for the source-table-driven pipeline used by `SOURCE_TYPE=csv` and `SOURCE_TYPE=mysql`.

## Top-level structure

```json
{
  "before_update": {
    "change_column_types": [],
    "add_indexes": [],
    "add_lookup_tables": {}
  },
  "after_update": {
    "add_indexes": [],
    "create_columns": [],
    "translate_concepts": []
  }
}
```

## `before_update`

These operations run before calculated-table creation/translations.

### `change_column_types`

Used to normalize imported source table column types before later processing.

Common fields:
- `destination_schema`
- `destination_table`
- `destination_column`
- `destination_column_type`

Example:

```json
{
  "destination_schema": "omop",
  "destination_table": "DIAGNOSIS_BRCAOVCA_HOSP_VW",
  "destination_column": "CONDITION_START_DATE",
  "destination_column_type": "DATE"
}
```

### `add_indexes`

Adds pre-update indexes to imported source tables to speed downstream operations.

Common fields:
- `destination_schema`
- `destination_table` or `destination_tables`
- `destination_column`
- `key_length`

Notes:
- In SQLite, prefix lengths from MySQL-style configs may be ignored or adapted.
- Some entries use `destination_tables` with a comma-separated list.

### `add_lookup_tables`

Describes lookup tables loaded from `lookup_tables/`.

Common fields:
- `lookup_schema`
- `lookup_tables_dir`
- `subdirectories`

Each subdirectory entry describes one lookup table family, including column metadata.

The current lookup family is `ICD_CODES`.

## `after_update`

These operations run after source ingestion and lookup setup.

### `add_indexes`

Adds indexes to downstream calculated tables such as:
- `CALCULATED_PT_ICD_CODES`
- `CALCULATED_DX_DATA`

### `create_columns`

This is a mixed section that drives:
- explicit column creation for calculated tables
- insert/update logic from source tables into calculated tables
- specialized operations like ICD code extraction

There are two broad entry shapes.

#### 1. Declarative column definitions

Example:

```json
{
  "destination_schema": "lookup",
  "destination_table": "CALCULATED_DX_DATA",
  "destination_column": "AGE_AT_DX",
  "destination_column_type": "INT",
  "destination_column_default": "NULL",
  "destination_column_nullable": "YES"
}
```

#### 2. Operation blocks

Example ICD operation:

```json
{
  "operation": {
    "destination_schema": "lookup",
    "source_schema": "omop",
    "type": "ICD",
    "tables": "DIAGNOSIS_BRCAOVCA_HOSP_VW,DIAGNOSIS_BRCAOVCA_OUTPT_VW,...",
    "code_column": "CONDITION_SOURCE_VALUE",
    "person_id_column": "PERSON_ID",
    "date_column": "CONDITION_START_DATE",
    "destination_table": "CALCULATED_PT_ICD_CODES"
  }
}
```

This is where much of the project-specific behavior lives.

#### Insert/update mappings

Some entries also describe how to move data from source tables into calculated tables.

Example:

```json
{
  "destination_schema": "lookup",
  "destination_table": "CALCULATED_PATIENT_DATA",
  "destination_column": "PERSON_ID",
  "source_schema": "omop",
  "source_tables": "DEMOGRAPHIC_BRCAOVCA_VW,DEMOGRAPHIC_MELANOMA_VW",
  "source_columns": "PERSON_ID,PERSON_ID",
  "join_on": "PERSON_ID",
  "verb": "INSERT"
}
```

## `translate_concepts`

This section maps source concept IDs to human-usable demographic values in `CALCULATED_PATIENT_DATA`.

Current concepts include:
- `GENDER`
- `RACE`
- `ETHNICITY`

Common fields:
- `source_schema`
- `source_tables`
- `source_column`
- `destination_schema`
- `destination_table`
- `destination_column`
- `concept`

Example:

```json
{
  "source_schema": "omop",
  "source_tables": "DEMOGRAPHIC_BRCAOVCA_VW,DEMOGRAPHIC_MELANOMA_VW",
  "destination_schema": "lookup",
  "destination_table": "CALCULATED_PATIENT_DATA",
  "destination_column": "GENDER",
  "source_column": "GENDER_CONCEPT_ID",
  "concept": "GENDER"
}
```

## Important caveats

1. `omop-config.js` primarily describes the `csv`/`mysql` path, not JSON mode.
2. Schema names like `omop` and `lookup` are logical grouping labels retained from earlier implementations; `omop` is not the public name of the database.
3. Some fields are MySQL-shaped even though the current destination is SQLite.
4. If you are debugging pipeline behavior, trace `run.py` -> `source/config_processor.py` -> `db/omop/*` helpers.

## How to work with this file safely

When revisiting the project:
1. Start with a single section, not the whole file.
2. Map each section to the function that consumes it.
3. Prefer additive edits with tests over broad refactors.
4. Re-run `uv run python -m unittest discover -s tests` after any config-driven code change.
