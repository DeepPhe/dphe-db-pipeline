# Scripts Directory - MIGRATION NEEDED

## Status: INCOMPLETE

The `src/scripts/` directory structure has been created, but the files haven't been moved yet.

## To Complete the Migration

Run the migration helper script from the project root:

```bash
python move_scripts.py
```

This will:
1. Copy all root-level scripts to `src/scripts/`
2. Update `Path(__file__).parent` to `Path(__file__).parent.parent.parent` in each file
3. Verify the files are ready to use

## Scripts to Be Moved

The following scripts will be moved from the project root to this directory:

- `create_concepts_table.py`
- `extract_cancers.py`
- `extract_cancers_data.py`
- `extract_concepts.py`
- `import_parsed_data.py`
- `parse_all_by_group.py`
- `parse_attributes_by_group.py`
- `parse_cancers_by_group.py`
- `parse_concepts_by_group.py`
- `parse_tumors_by_group.py`
- `query_tumors.py`
- `query_tumors_adenocarcinoma_breastlump.py`

## After Migration

Once the migration is complete:

1. Test the scripts from their new location:
   ```bash
   python src/scripts/import_parsed_data.py
   python src/scripts/parse_all_by_group.py
   python src/scripts/query_tumors.py --list
   ```

2. If all tests pass, optionally delete the old root files:
   ```bash
   rm create_concepts_table.py extract_*.py import_*.py parse_*.py query_*.py
   ```

3. Update `.gitignore` to ignore old root files

## Why This Wasn't Done Automatically

Due to file size constraints, the automated migration couldn't complete. The `move_scripts.py` helper has been created to finish the job.

## Manual Alternative

If you prefer to move files manually:

1. Copy each script from root to `src/scripts/`
2. In each file, replace:
   ```python
   base_dir = Path(__file__).parent
   ```
   with:
   ```python
   base_dir = Path(__file__).parent.parent.parent
   ```

3. Test each script works from new location
