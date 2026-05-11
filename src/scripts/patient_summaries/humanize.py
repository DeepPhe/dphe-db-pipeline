"""
classUri humanization -- convert raw DeepPhe URIs to human-readable labels.
"""

from __future__ import annotations

import re
from typing import Dict

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_STAGE_SUFFIX_RE = re.compile(r"^(P?)(.+?)StageFinding$", re.IGNORECASE)
_CAMEL_SPLIT_RE = re.compile(
    r"(?<=[a-z])(?=[A-Z])"        # camelCase boundary
    r"|(?<=[A-Z])(?=[A-Z][a-z])"  # ACRONYMWord boundary
    r"|(?<=[a-z])(?=\d)"          # word -> digit boundary  (Status0)
    r"|(?<=\d)(?=[A-Z][a-z])"     # digit -> Word boundary  (SOX10Gene)
)
# Matches a bare underscore between word characters, EXCLUDING the multi-char
# special tokens (_sl_, _sub_, _lpn_, _rpn_, _cma_, _qt_, _dot_) which are
# handled upstream.
_BARE_UNDERSCORE_RE = re.compile(r"(?<=\w)_(?=\w)")
_SL_SEP = "_sl_"

# Clock position pattern:  n_10O_qt_clockPosition, n_2_dot_30O_qt_clockPosition
_CLOCK_RE = re.compile(
    r"^n_(\d+)(?:_dot_(\d+))?O_qt_clockPosition$", re.IGNORECASE
)

# Known chemo regimen abbreviation map (extend as needed).
_REGIMEN_ABBREV: Dict[str, str] = {
    "Cisplatin_sl_Cyclophosphamide_sl_Doxorubicin": "CAP",
    "Cyclophosphamide_sl_Doxorubicin_sl_Fluorouracil": "CAF",
    "Cyclophosphamide_sl_Methotrexate_sl_Fluorouracil": "CMF",
}


def humanize_class_uri(uri: str) -> str:
    """Convert a raw classUri into a human-readable label.

    Rules applied in order:
    1. Clock positions: ``n_10O_qt_clockPosition`` -> ``10 o\'clock position``
    2. Staging suffixes: ``PT1sStageFinding`` -> ``pT1s``
    3. ``_sl_``-delimited chemo regimens: split + optional abbreviation
    4. ``_cma_`` -> ``, `` (comma separator in subtypes)
    5. ``_sub_`` -> ``-`` (subscript separator in gene products)
    6. Parenthesized tokens (``_lpn_`` / ``_rpn_``): restored as ``(`` / ``)``
    7. ``_dot_`` -> ``.`` (decimal separator)
    8. ``_qt_`` -> ``\'`` (apostrophe / quote marker)
    9. CamelCase splitting + bare underscores -> hyphens
    """
    # Clock positions (must check before general CamelCase)
    clock_m = _CLOCK_RE.match(uri)
    if clock_m:
        hour = clock_m.group(1)
        minutes = clock_m.group(2)
        if minutes:
            return f"{hour}:{minutes} o\'clock position"
        return f"{hour} o\'clock position"

    # Stage findings
    m = _STAGE_SUFFIX_RE.match(uri)
    if m:
        prefix_letter = m.group(1).lower()  # "" or "p"
        body = m.group(2)
        return f"{prefix_letter}{body}"

    # Chemo regimens with _sl_ separator
    if _SL_SEP in uri:
        # Apply all special-token replacements inside each fragment
        drugs = []
        for frag in uri.split(_SL_SEP):
            frag = frag.replace("_cma_", ", ")
            frag = frag.replace("_sub_", "-")
            frag = frag.replace("_lpn_", " (").replace("_rpn_", ")")
            frag = frag.replace("_dot_", ".")
            frag = frag.replace("_qt_", "\'")
            drugs.append(_camel_to_words(frag))
        label = " / ".join(drugs)
        abbrev = _REGIMEN_ABBREV.get(uri)
        if abbrev:
            label = f"{label} ({abbrev})"
        return label

    # Comma separator in cancer subtypes (before _sub_ to avoid conflicts)
    cleaned = uri.replace("_cma_", ", ")

    # Subscript / bond separator in gene products: Cyclin_sub_Dependent -> Cyclin-Dependent
    cleaned = cleaned.replace("_sub_", "-")

    # Parenthesized tokens
    cleaned = cleaned.replace("_lpn_", " (").replace("_rpn_", ")")

    # Decimal separator
    cleaned = cleaned.replace("_dot_", ".")

    # Apostrophe / quote marker
    cleaned = cleaned.replace("_qt_", "\'")

    # Slash separator (guard against leftover _sl_ fragments)
    cleaned = cleaned.replace("_sl_", " / ")

    # CamelCase split + remaining bare underscores -> hyphens
    return _camel_to_words(cleaned)


def _camel_to_words(text: str) -> str:
    """Split CamelCase into space-separated words, then convert bare _ to -."""
    spaced = _CAMEL_SPLIT_RE.sub(" ", text)
    return _BARE_UNDERSCORE_RE.sub("-", spaced)
