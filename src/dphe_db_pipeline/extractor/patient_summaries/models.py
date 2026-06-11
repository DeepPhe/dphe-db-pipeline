"""
Data classes for patient summary generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    attribute_name: str | None = None  # only for attributes_by_group


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
    demographics: dict[str, str | None] = field(default_factory=dict)
    diagnoses: list[dict[str, Any]] = field(default_factory=list)
    staging: list[dict[str, Any]] = field(default_factory=list)
    grading: list[dict[str, Any]] = field(default_factory=list)
    biomarkers: list[dict[str, Any]] = field(default_factory=list)
    procedures: list[dict[str, Any]] = field(default_factory=list)
    treatments: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    behavior: list[dict[str, Any]] = field(default_factory=list)
    anatomy: list[dict[str, Any]] = field(default_factory=list)
    clinical_course: list[dict[str, Any]] = field(default_factory=list)
    qualifiers: list[dict[str, Any]] = field(default_factory=list)
    cancers: list[dict[str, Any]] = field(default_factory=list)
    tumors: list[dict[str, Any]] = field(default_factory=list)
    other_concepts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
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

def _hit_to_dict(hit: ConceptHit) -> dict[str, Any]:
    """Convert a ConceptHit to a display-ready dict (no internal fields)."""
    d: dict[str, Any] = {"name": hit.name}
    if hit.negated:
        d["negated"] = True
    if hit.uncertain:
        d["uncertain"] = True
    if hit.historic:
        d["historic"] = True
    return d
