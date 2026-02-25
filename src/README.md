# Source Code Structure

This directory contains the source code for DeepPheConceptExtractor, organized by functionality.

## Directory Structure

```
src/
├── analysis/           # Data analysis and reporting scripts
├── scripts/            # Main execution scripts (planned)
└── utils/              # Utility functions and helper scripts
```

## Modules

### analysis/
Analysis scripts for exploring and reporting on extracted data.

**Scripts:**
- `top_25_by_patients.py` - List top 25 items from each _by_group table

**Usage:**
```bash
python src/analysis/top_25_by_patients.py
```

### utils/
Utility scripts for database exploration and file manipulation.

**Scripts:**
- `check_encodings.py` - Check file encodings in database
- `explore_database.py` - Explore database schema and structure  
- `split_csv_files.py` - Split large CSV files into patient-based chunks

**Usage:**
```bash
python src/utils/check_encodings.py
python src/utils/explore_database.py
python src/utils/split_csv_files.py
```

### scripts/ (Planned)
Main execution scripts for data extraction, parsing, and querying.

Scripts currently in root directory will be moved here:
- `extract_cancers.py`, `extract_cancers_data.py`, `extract_concepts.py`
- `create_concepts_table.py`
- `import_parsed_data.py`
- `parse_all_by_group.py`, `parse_*_by_group.py`
- `query_tumors.py`, `query_tumors_adenocarcinoma_breastlump.py`

## Development Guidelines

### Adding New Scripts

1. **Determine category:**
   - **analysis/** - Data analysis, reporting, statistics
   - **scripts/** - Main execution, data processing
   - **utils/** - Helper functions, database tools

2. **Follow naming conventions:**
   - Use descriptive snake_case names
   - Prefix with category (e.g., `analyze_`, `extract_`, `query_`)

3. **Include proper structure:**
   ```python
   #!/usr/bin/env python3
   """
   Module docstring describing purpose.
   """
   
   def main():
       """Main entry point."""
       pass
   
   if __name__ == "__main__":
       main()
   ```

4. **Handle paths correctly:**
   ```python
   from pathlib import Path
   
   # Get project root (3 levels up from src/category/script.py)
   base_dir = Path(__file__).parent.parent.parent
   db_path = base_dir / "deepphe" / "deepphe_sqlite_compressed"
   ```

### Code Standards

- Follow PEP 8
- Use type hints
- Include docstrings
- Add logging for long-running operations
- Handle errors gracefully
- Keep functions focused and testable

## Migration Status

**Completed:**
- ✅ `src/analysis/` - Created and populated
- ✅ `src/utils/` - Created and populated  
- ✅ `tests/` - Created and populated

**Planned:**
- ⏳ `src/scripts/` - To be populated with root-level scripts
- ⏳ `src/core/` - Shared library code (if needed)

## Running Scripts

All scripts can be run from the project root:

```bash
# Analysis
python src/analysis/top_25_by_patients.py

# Utilities  
python src/utils/check_encodings.py
python src/utils/explore_database.py
python src/utils/split_csv_files.py

# Tests
python tests/test_parse_concepts.py

# Scripts still in root (backward compatibility)
python extract_cancers_data.py
python import_parsed_data.py
python parse_all_by_group.py
python query_tumors.py --list
```

## Future Improvements

1. Create `src/scripts/` and move all execution scripts
2. Extract shared code into `src/core/` library modules
3. Add proper logging configuration
4. Create CLI entry points in `pyproject.toml`
5. Build installable package structure
