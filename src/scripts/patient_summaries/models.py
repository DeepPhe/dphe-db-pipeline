"""
Data classes for patient summary generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import SLIM_MODE

# ---------------------------------------------------------------------------
# ConceptHit
# ---------------------------------------------------------------------------

@dataclass
class ConceptHit:
    """One concept/attribute row that matched a patient\'s bitmap."""
    name: str                   # humanized classUri
    raw_uri: str                # original classUri for debugging
    bucket: str                 # summary bucket key
    source_table: str           # e.g. "concepts", "cancers", "attributes"
    negated: bool = False
    uncertain: bool = False
    historic: bool = False
    attribute_name: Optional[str] = None  # only for attributes_by_group


# ---------------------------------------------------------------------------
# Bucket lists
# ---------------------------------------------------------------------------

# Buckets emitted when SLIM_MODE is False (full output).
_ALL_BUCKETS = (
    "diagnoses", "staging", "grading", "biomarkers", "procedures",
    "treatments", "findings", "behavior", "anatomy",
    "clinical_course", "qualifiers", "cancers", "tumors",
    "other_concepts",
)

# Buckets suppressed from output in slim mode.
_SLIM_SUPPRESSED = {"qualifiers", "anatomy", "clinical_course", "other_concepts"}


# ---------------------------------------------------------------------------
# PatientSummary
# ---------------------------------------------------------------------------

@dataclass
class PatientSummary:
    """Aggregated patient summary, serializable to JSON."""
    patient_id: str
    sequential_id: int
    demographics: Dict[str, Optional[str]] = field(default_factory=dict)
    diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    staging: List[Dict[str, Any]] = field(default_factory=list)
    grading: List[Dict[str, Any]] = field(default_factory=list)
    biomarkers: List[Dict[str, Any]] = field(default_factory=list)
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    treatments: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    behavior: List[Dict[str, Any]] = field(default_factory=list)
    anatomy: List[Dict[str, Any]] = field(default_factory=list)
    clinical_course: List[Dict[str, Any]] = field(default_factory=list)
    qualifiers: List[Dict[str, Any]] = field(default_factory=list)
    cancers: List[Dict[str, Any]] = field(default_factory=list)
    tumors: List[Dict[str, Any]] = field(default_factory=list)
    other_concepts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "patient_id": self.patient_id,
            "sequential_id": self.sequential_id,
            "demographics": self.demographics,
        }
        for bucket in _ALL_BUCKETS:
            if SLIM_MODE and bucket in _SLIM_SUPPRESSED:
                continue
            items = getattr(self, bucket)
            if items:
                d[bucket] = items
        return d


# ---------------------------------------------------------------------------
# IndexedRow
# ---------------------------------------------------------------------------

@dataclass
class IndexedRow:
    """Pre-deserialized bitmap row from any *_by_group table."""
    bitmap: Any  # pyroaring.BitMap (Any to avoid hard import in tests)
    hit_factory: Any  # callable(sequential_id) -> ConceptHit or None


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------

def _hit_to_dict(hit: ConceptHit) -> Dict[str, Any]:
    """Convert a ConceptHit to a display-ready dict (no internal fields)."""
    d: Dict[str, Any] = {"name": hit.name}
    if hit.negated:
        d["negated"] = True
    if hit.uncertain:
        d["uncertain"] = True
    if hit.historic:
        d["historic"] = True
    return d
