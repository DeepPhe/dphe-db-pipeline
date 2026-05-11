"""
Post-processing: dedup, merge, and reclassify patient summary buckets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .config import (
    GENE_PRODUCTS_NOT_TREATMENTS,
    GENE_PRODUCT_SUFFIXES,
    IHC_STAINS,
    RECEPTOR_STATUS_NAMES,
    ROUTINE_EXAM_PROCEDURES,
)
from .models import PatientSummary, _ALL_BUCKETS


def _dedup_bucket(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and merge items within a single bucket.

    1. Cross-table duplicates: same (name, negated) -> keep the richest entry.
    2. Affirmed/negated conflict: same name with both -> keep affirmed,
       add ``conflicted: true``.
    """
    # Pass 1: collapse exact (name, negated) duplicates.
    merged: Dict[Tuple[str, bool], Dict[str, Any]] = {}
    for item in items:
        name = item["name"]
        neg = item.get("negated", False)
        key = (name, neg)

        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(item)
        else:
            # Keep the entry with more modifier keys (uncertain, historic).
            if len(item) > len(existing):
                merged[key] = dict(item)

    # Pass 2: resolve affirmed/negated conflicts on the same name.
    by_name: Dict[str, List[Tuple[str, bool]]] = {}
    for key in merged:
        by_name.setdefault(key[0], []).append(key)

    result: Dict[Tuple[str, bool], Dict[str, Any]] = {}
    for name, keys in by_name.items():
        if len(keys) == 1:
            result[keys[0]] = merged[keys[0]]
            continue

        affirmed_key = (name, False)
        negated_key = (name, True)
        affirmed = merged.get(affirmed_key)
        negated = merged.get(negated_key)

        if affirmed and negated:
            winner = dict(affirmed)
            winner.pop("negated", None)
            winner["conflicted"] = True
            result[affirmed_key] = winner
        elif affirmed:
            result[affirmed_key] = affirmed
        elif negated:
            result[negated_key] = negated

    return list(result.values())


def _dedup_staging(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pathologic (p-prefix) wins over clinical for the same stage value."""
    names = {item["name"] for item in items}
    pathologic_bases: Set[str] = set()
    for n in names:
        if n.startswith("p") and len(n) > 1:
            pathologic_bases.add(n[1:])

    if not pathologic_bases:
        return items

    return [item for item in items if item["name"] not in pathologic_bases]


def _is_gene_product(name: str) -> bool:
    """Return True if the humanized name looks like a gene product, not a drug."""
    if name in GENE_PRODUCTS_NOT_TREATMENTS:
        return True
    # Suffix heuristic
    for suffix in GENE_PRODUCT_SUFFIXES:
        if name.endswith(suffix):
            return True
    return False


def _merge_modifiers(
    target: Dict[str, Any], source: Dict[str, Any]
) -> None:
    """Copy uncertain/historic/conflicted from source into target if missing."""
    for key in ("uncertain", "historic", "conflicted"):
        if source.get(key) and not target.get(key):
            target[key] = True


def _names_set(items: List[Dict[str, Any]]) -> Set[str]:
    """Return the set of names in a bucket list."""
    return {item["name"] for item in items}


def _item_by_name(items: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    """Find the first item with the given name, or None."""
    for item in items:
        if item["name"] == name:
            return item
    return None


def dedup_and_merge(summary: PatientSummary) -> PatientSummary:
    """Post-process a patient summary: dedup, merge conflicts, reclassify.

    Execution order:
    1. Cross-bucket dedup: treatments duplicated in biomarkers/procedures/findings
    2. Gene product reclassification: treatments -> biomarkers
    3. IHC stain reclassification: treatments -> biomarkers
    4. Routine exam removal: strip non-oncology procedures + treatments
    5. Receptor status migration: findings -> biomarkers
    6. Cancer/tumor merge into diagnoses: merge + delete buckets
    7. Final intra-bucket dedup on all buckets
    """

    # --- 1. Cross-bucket dedup: treatments that exist in a more specific bucket ---
    specific_names = _names_set(summary.biomarkers) | _names_set(summary.procedures) | _names_set(summary.findings)
    remaining_treatments: List[Dict[str, Any]] = []
    for item in summary.treatments:
        if item["name"] in specific_names:
            # Merge modifiers from treatments version into the existing copy
            for bucket in (summary.biomarkers, summary.procedures, summary.findings):
                existing = _item_by_name(bucket, item["name"])
                if existing is not None:
                    _merge_modifiers(existing, item)
                    break
        else:
            remaining_treatments.append(item)
    summary.treatments = remaining_treatments

    # --- 2. Gene product reclassification: treatments -> biomarkers ---
    remaining_treatments = []
    for item in summary.treatments:
        if item["name"] in IHC_STAINS or _is_gene_product(item["name"]):
            # Only add if not already present in biomarkers
            if item["name"] not in _names_set(summary.biomarkers):
                summary.biomarkers.append(item)
            else:
                existing = _item_by_name(summary.biomarkers, item["name"])
                if existing is not None:
                    _merge_modifiers(existing, item)
        else:
            remaining_treatments.append(item)
    summary.treatments = remaining_treatments

    # --- 3. Routine exam removal ---
    summary.procedures = [
        item for item in summary.procedures
        if item["name"] not in ROUTINE_EXAM_PROCEDURES
    ]
    summary.treatments = [
        item for item in summary.treatments
        if item["name"] not in ROUTINE_EXAM_PROCEDURES
    ]

    # --- 4. Receptor status migration: findings -> biomarkers ---
    remaining_findings: List[Dict[str, Any]] = []
    for item in summary.findings:
        if item["name"] in RECEPTOR_STATUS_NAMES:
            if item["name"] not in _names_set(summary.biomarkers):
                summary.biomarkers.append(item)
            else:
                existing = _item_by_name(summary.biomarkers, item["name"])
                if existing is not None:
                    _merge_modifiers(existing, item)
        else:
            remaining_findings.append(item)
    summary.findings = remaining_findings

    # --- 5. Cancer/tumor merge into diagnoses ---
    dx_names = _names_set(summary.diagnoses)
    for source_bucket in (summary.cancers, summary.tumors):
        source_label = "cancer" if source_bucket is summary.cancers else "tumor"
        for item in source_bucket:
            name = item["name"]
            if name in dx_names:
                # Merge modifiers into the existing diagnoses entry
                existing = _item_by_name(summary.diagnoses, name)
                if existing is not None:
                    _merge_modifiers(existing, item)
            else:
                # Move into diagnoses with a source tag
                new_item = dict(item)
                new_item["source"] = source_label
                summary.diagnoses.append(new_item)
                dx_names.add(name)
    summary.cancers = []
    summary.tumors = []

    # --- 6. Final intra-bucket dedup (since reclassification added items) ---
    for bucket_name in _ALL_BUCKETS:
        items = getattr(summary, bucket_name)
        if not items:
            continue
        deduped = _dedup_bucket(items)
        if bucket_name == "staging":
            deduped = _dedup_staging(deduped)
        setattr(summary, bucket_name, deduped)

    return summary
