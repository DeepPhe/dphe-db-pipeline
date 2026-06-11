"""Decode content blobs stored by the Stage 1 loader."""

from __future__ import annotations

from typing import Any, cast

zstd: Any
try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    zstd = None


def decode_stored_content(content: Any, encoding: str) -> str:
    """Return text content from a raw or compressed SQLite blob value."""
    if isinstance(content, str):
        return content
    if not isinstance(content, bytes):
        return str(content)

    normalized_encoding = (encoding or "").lower()
    if normalized_encoding == "zstd":
        if not ZSTD_AVAILABLE:
            raise ImportError(
                "zstandard library required for zstd decompression. "
                "Install with: pip install zstandard"
            )
        decompressor = zstd.ZstdDecompressor()
        decompressed = cast(bytes, decompressor.decompress(content))
        return decompressed.decode("utf-8")

    if normalized_encoding == "raw":
        return content.decode("utf-8", errors="replace")

    codec = encoding if normalized_encoding != "none" else "utf-8"
    try:
        return content.decode(codec)
    except (LookupError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")
