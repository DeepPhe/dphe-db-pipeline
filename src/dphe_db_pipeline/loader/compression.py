"""Compression helpers for Stage 1 SQLite blob storage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CompressorFn = Callable[[bytes], bytes]


def build_compressor(algo: str, level: int) -> tuple[str, Any, CompressorFn]:
    """Return the normalized algorithm name, compressor object, and compression function."""
    algo = (algo or "zstd").lower()
    if algo in {"none", "raw"}:
        return "raw", None, lambda data: data

    if algo == "zstd":
        try:
            import zstandard as zstd
        except ImportError as exc:
            raise RuntimeError(
                "zstandard package is required for --compress zstd. "
                "Install with: pip install zstandard"
            ) from exc
        compressor = zstd.ZstdCompressor(level=level)
        return "zstd", compressor, compressor.compress

    if algo == "lz4":
        try:
            import lz4.frame as lz4f
        except ImportError as exc:
            raise RuntimeError(
                "lz4 package is required for --compress lz4. Install with: pip install lz4"
            ) from exc
        return "lz4", None, lambda data: lz4f.compress(data, compression_level=level)

    raise ValueError(f"Unsupported compression algorithm: {algo}")


def maybe_compress(
    data: bytes,
    algo_name: str,
    compress_fn: CompressorFn,
    min_bytes: int,
) -> tuple[bytes, str]:
    """Compress data if it is large enough and compression reduces the byte size."""
    if algo_name == "raw":
        return data, "raw"
    if len(data) < max(0, int(min_bytes)):
        return data, "raw"

    try:
        compressed = compress_fn(data)
    except Exception:
        return data, "raw"

    if len(compressed) < len(data):
        return compressed, algo_name
    return data, "raw"
