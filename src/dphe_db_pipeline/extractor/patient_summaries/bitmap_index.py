"""
Bitmap index -- preload all rows once, test membership per patient.
"""

from __future__ import annotations

import sqlite3

from pyroaring import BitMap

from .config import ATTRIBUTE_BUCKET, DPHE_GROUP_BUCKET
from .humanize import humanize_class_uri
from .models import ConceptHit, IndexedRow


def _deserialize_bitmap(blob: bytes) -> BitMap:
    return BitMap.deserialize(blob)


def preload_concepts(conn: sqlite3.Connection) -> list[IndexedRow]:
    """Load all concepts_by_group rows with deserialized bitmaps."""
    rows: list[IndexedRow] = []
    cur = conn.execute(
        "SELECT dpheGroup, classUri, negated, patient_bitmap FROM concepts_by_group"
    )
    for dphe_group, class_uri, negated, blob in cur:
        bm = _deserialize_bitmap(blob)
        bucket = DPHE_GROUP_BUCKET.get(dphe_group, "other_concepts")
        name = humanize_class_uri(class_uri)
        neg = bool(negated)

        def factory(_sid, _name=name, _uri=class_uri, _bucket=bucket, _neg=neg, _grp=dphe_group):
            return ConceptHit(
                name=_name, raw_uri=_uri, bucket=_bucket,
                source_table="concepts", negated=_neg,
            )

        rows.append(IndexedRow(bitmap=bm, hit_factory=factory))
    return rows


def preload_cancers(conn: sqlite3.Connection) -> list[IndexedRow]:
    rows: list[IndexedRow] = []
    cur = conn.execute(
        "SELECT classUri, negated, uncertain, historic, patient_bitmap FROM cancers_by_group"
    )
    for class_uri, negated, uncertain, historic, blob in cur:
        bm = _deserialize_bitmap(blob)
        name = humanize_class_uri(class_uri)
        neg, unc, hist = bool(negated), bool(uncertain), bool(historic)

        def factory(_sid, _name=name, _uri=class_uri, _neg=neg, _unc=unc, _hist=hist):
            return ConceptHit(
                name=_name, raw_uri=_uri, bucket="cancers",
                source_table="cancers", negated=_neg, uncertain=_unc, historic=_hist,
            )
        rows.append(IndexedRow(bitmap=bm, hit_factory=factory))
    return rows


def preload_tumors(conn: sqlite3.Connection) -> list[IndexedRow]:
    rows: list[IndexedRow] = []
    cur = conn.execute(
        "SELECT classUri, negated, uncertain, historic, patient_bitmap FROM tumors_by_group"
    )
    for class_uri, negated, uncertain, historic, blob in cur:
        bm = _deserialize_bitmap(blob)
        name = humanize_class_uri(class_uri)
        neg, unc, hist = bool(negated), bool(uncertain), bool(historic)

        def factory(_sid, _name=name, _uri=class_uri, _neg=neg, _unc=unc, _hist=hist):
            return ConceptHit(
                name=_name, raw_uri=_uri, bucket="tumors",
                source_table="tumors", negated=_neg, uncertain=_unc, historic=_hist,
            )
        rows.append(IndexedRow(bitmap=bm, hit_factory=factory))
    return rows


def preload_attributes(conn: sqlite3.Connection) -> list[IndexedRow]:
    rows: list[IndexedRow] = []
    cur = conn.execute(
        "SELECT attribute_name, classUri, negated, uncertain, historic, patient_bitmap "
        "FROM attributes_by_group"
    )
    for attr_name, class_uri, negated, uncertain, historic, blob in cur:
        bm = _deserialize_bitmap(blob)
        bucket = ATTRIBUTE_BUCKET.get(attr_name, "other_concepts")
        name = humanize_class_uri(class_uri)
        neg, unc, hist = bool(negated), bool(uncertain), bool(historic)

        def factory(
            _sid, _name=name, _uri=class_uri, _bucket=bucket,
            _neg=neg, _unc=unc, _hist=hist, _attr=attr_name,
        ):
            return ConceptHit(
                name=_name, raw_uri=_uri, bucket=_bucket,
                source_table="attributes", negated=_neg,
                uncertain=_unc, historic=_hist, attribute_name=_attr,
            )
        rows.append(IndexedRow(bitmap=bm, hit_factory=factory))
    return rows
