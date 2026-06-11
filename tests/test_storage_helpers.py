"""Tests for Stage 1 storage helper behavior."""

from dphe_db_pipeline.extractor.stored_content import decode_stored_content
from dphe_db_pipeline.loader.compression import build_compressor, maybe_compress


def test_maybe_compress_keeps_raw_when_compression_does_not_help() -> None:
    algo_name, _compressor, compress_fn = build_compressor("zstd", 1)

    stored, encoding = maybe_compress(b"x", algo_name, compress_fn, min_bytes=0)

    assert stored == b"x"
    assert encoding == "raw"


def test_zstd_round_trip_decodes_stored_content() -> None:
    payload = b"DeepPhe example payload " * 20
    algo_name, _compressor, compress_fn = build_compressor("zstd", 1)
    stored, encoding = maybe_compress(payload, algo_name, compress_fn, min_bytes=0)

    assert encoding == "zstd"
    assert decode_stored_content(stored, encoding) == payload.decode("utf-8")


def test_raw_bytes_decode_with_replacement() -> None:
    assert decode_stored_content(b"ok\xff", "raw") == "ok\ufffd"
