"""
Configuration constants for patient summary generation.

Edit this file to tune bucket mappings, slim output, or domain heuristics.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Output mode
# ---------------------------------------------------------------------------

# When True, suppress low-value buckets (qualifiers, anatomy, clinical_course,
# other_concepts) from the generated JSONL.
SLIM_MODE: bool = False


# ---------------------------------------------------------------------------
# dpheGroup -> summary bucket mapping
# ---------------------------------------------------------------------------

DPHE_GROUP_BUCKET: dict[str, str] = {
    "Neoplasm":                             "diagnoses",
    "Disease or Disorder":                  "diagnoses",
    "Disease Stage Qualifier":              "staging",
    "Generic TNM Finding":                  "staging",
    "Pathologic TNM Finding":               "staging",
    "Disease Grade Qualifier":              "grading",
    "Gene":                                 "biomarkers",
    "Gene Product":                         "biomarkers",
    "Clinical Test Result":                 "findings",
    "Finding":                              "findings",
    "Mass":                                 "findings",
    "Pathologic Process":                   "findings",
    "Intervention or Procedure":            "procedures",
    "Chemo/immuno/hormone Therapy Regimen": "treatments",
    "Pharmacologic Substance":              "treatments",
    "Behavior":                             "behavior",
    "Body Part":                            "anatomy",
    "Lymph Node":                           "anatomy",
    "Organ System":                         "anatomy",
    "Tissue":                               "anatomy",
    "Clinical Course of Disease":           "clinical_course",
    "Disease Qualifier":                    "qualifiers",
    "General Qualifier":                    "qualifiers",
    "Side":                                 "qualifiers",
    "Spatial Qualifier":                    "qualifiers",
    "Temporal Qualifier":                   "qualifiers",
    # Catch-all for remaining groups
    "Body Fluid or Substance":              "other_concepts",
    "Dose":                                 "other_concepts",
    "Property or Attribute":               "other_concepts",
}


# ---------------------------------------------------------------------------
# attribute_name -> summary bucket mapping
# ---------------------------------------------------------------------------

ATTRIBUTE_BUCKET: dict[str, str] = {
    # Staging
    "stage":                    "staging",
    "tnmT":                     "staging",
    "tnmN":                     "staging",
    "tnmM":                     "staging",
    "tnm_t":                    "staging",
    "tnm_n":                    "staging",
    "tnm_m":                    "staging",
    "clinical_stage":           "staging",
    "pathologic_stage":         "staging",
    # Grading
    "grade":                    "grading",
    "histology":                "grading",
    "histologic_grade":         "grading",
    # Biomarkers / receptor status
    "er_status":                "biomarkers",
    "pr_status":                "biomarkers",
    "her2_status":              "biomarkers",
    "ki67":                     "biomarkers",
    "brca":                     "biomarkers",
    "brca1":                    "biomarkers",
    "brca2":                    "biomarkers",
    "pdl1":                     "biomarkers",
    # Anatomy
    "site":                     "anatomy",
    "laterality":               "anatomy",
    "quadrant":                 "anatomy",
    # Behavior
    "behavior":                 "behavior",
    # Findings
    "metastasis":               "findings",
    "tumor_size":               "findings",
}


# ---------------------------------------------------------------------------
# Postprocessing heuristics (used by postprocess.py)
# ---------------------------------------------------------------------------

# Gene products that should stay in biomarkers rather than be treated as drugs.
GENE_PRODUCTS_NOT_TREATMENTS: frozenset[str] = frozenset({
    "BRCA1", "BRCA2", "HER2", "ER", "PR",
    "Ki-67", "PD-L1", "ALK", "EGFR", "KRAS",
    "PIK3CA", "TP53", "PTEN", "CDH1", "RB1",
    "MLH1", "MSH2", "MSH6", "PMS2", "ATM",
    "PALB2", "RAD51C", "RAD51D", "CHEK2",
})

# Humanized name suffixes that indicate a gene product (not a treatment drug).
GENE_PRODUCT_SUFFIXES: tuple[str, ...] = (
    " Gene", " Protein", " Receptor", " Kinase",
    " Ligand", " Factor", " Antigen",
)

# IHC panel stains -- should be reclassified from treatments to biomarkers.
IHC_STAINS: frozenset[str] = frozenset({
    "Estrogen Receptor", "Progesterone Receptor",
    "HER2/neu", "Ki-67", "PD-L1",
    "CD3", "CD4", "CD8", "CD20", "CD30", "CD45",
    "Cytokeratin", "E-Cadherin", "Vimentin",
    "S-100", "Melan-A", "SOX10",
    "p53", "p16", "p63",
})

# Receptor status concept names -- migrated from findings to biomarkers.
RECEPTOR_STATUS_NAMES: frozenset[str] = frozenset({
    "Estrogen Receptor Positive",
    "Estrogen Receptor Negative",
    "Progesterone Receptor Positive",
    "Progesterone Receptor Negative",
    "HER2 Positive",
    "HER2 Negative",
    "Triple Negative",
    "Hormone Receptor Positive",
    "Hormone Receptor Negative",
})

# Routine / non-oncology procedures to strip from output.
ROUTINE_EXAM_PROCEDURES: frozenset[str] = frozenset({
    "Physical Examination",
    "Blood Test",
    "Complete Blood Count",
    "Urinalysis",
    "Vital Signs",
    "Weight Measurement",
    "Blood Pressure Measurement",
})

