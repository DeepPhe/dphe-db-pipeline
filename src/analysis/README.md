# Analysis Module

Scripts for analyzing DeepPhe extracted data.

## Scripts

### top_25_by_patients.py

List the top 25 most common items from each aggregated table, ranked by patient count.

**Usage:**
```bash
python src/analysis/top_25_by_patients.py
```

**Output:**
- Top 25 attributes by patient count
- Top 25 cancers by patient count
- Top 25 concepts by patient count
- Top 25 tumors by patient count
- Summary statistics

**Documentation:** See `.ai/md/top_25_analysis.md`

## Requirements

- Database must be imported: `python import_parsed_data.py`
- pyroaring library (for bitmap operations): `pip install pyroaring`

## Directory Structure

```
src/analysis/
├── __init__.py              # Package initialization
├── README.md                # This file
└── top_25_by_patients.py    # Top 25 analysis script
```

## Future Scripts

Additional analysis scripts can be added here:
- Cohort discovery tools
- Statistical analysis
- Trend analysis
- Data quality reports


