# Tests

Test suite for DeepPheConceptExtractor.

## Structure

```
tests/
├── __init__.py
└── test_parse_concepts.py
```

## Running Tests

### Individual Test
```bash
python tests/test_parse_concepts.py
```

### All Tests (using pytest)
```bash
pytest tests/
```

## Test Files

### test_parse_concepts.py
Tests the concept parsing logic by loading and parsing `extracted_concepts.csv`.

**What it tests:**
- CSV parsing functionality
- Concept grouping by dpheGroup, classUri, and negated status
- Patient aggregation across concepts
- Statistics calculation

**Expected output:**
- Sample of parsed concepts
- Statistics (total concepts, patients, negated vs non-negated)
- Top 10 most common concepts by patient count

## Adding New Tests

When adding new tests, follow these guidelines:

1. **Name test files** with `test_` prefix (e.g., `test_parse_attributes.py`)

2. **Structure test functions:**
   ```python
   def test_function_name():
       """Test description."""
       # Arrange
       ...
       
       # Act
       ...
       
       # Assert
       assert result == expected
   ```

3. **Use pytest fixtures** for common setup:
   ```python
   import pytest
   
   @pytest.fixture
   def sample_data():
       return {...}
   
   def test_with_fixture(sample_data):
       assert sample_data is not None
   ```

4. **Test edge cases:**
   - Empty inputs
   - Invalid data
   - Missing files
   - Large datasets

## Test Coverage

To generate coverage reports:

```bash
pytest --cov=src tests/
```

## Current Coverage

- ✅ Concept parsing logic
- ⏳ Attribute parsing
- ⏳ Cancer/tumor parsing  
- ⏳ Database operations
- ⏳ Bitmap operations

## Future Tests

Planned test coverage:

- [ ] `test_parse_attributes.py` - Test attribute parsing
- [ ] `test_parse_cancers.py` - Test cancer parsing
- [ ] `test_parse_tumors.py` - Test tumor parsing
- [ ] `test_import_data.py` - Test database import functionality
- [ ] `test_bitmaps.py` - Test bitmap operations
- [ ] `test_queries.py` - Test query functionality
- [ ] `test_analysis.py` - Test analysis scripts

## Test Data

Test files should use sample data when possible to avoid dependencies on large files:

```python
# Good - uses small sample
def test_parse_with_sample():
    data = [
        {"patient_id": "1", "dpheGroup": "Test", ...},
        {"patient_id": "2", "dpheGroup": "Test", ...},
    ]
    result = parse_data(data)
    assert len(result) == 2

# Avoid - depends on large external file
def test_parse_with_full_data():
    result = parse_csv("extracted_cancer_data/huge_file.csv")
    ...
```

## Continuous Integration

When CI is set up, tests will run automatically on:
- Pull requests
- Commits to main branch
- Scheduled daily runs

## Debugging Tests

Run with verbose output:
```bash
pytest -v tests/

# With stdout
pytest -v -s tests/

# Stop on first failure
pytest -x tests/

# Run specific test
pytest tests/test_parse_concepts.py::test_function_name
```
