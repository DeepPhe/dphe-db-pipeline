"""Stage 1 loader input-mode tests: directory, single zip, and zip directory.

These exercise the three code paths behind ``--input-dir`` / ``--input-zip`` /
``--input-zipdir`` in ``load_files_to_db``. Inputs are synthesized in ``tmp_path`` so
no binary fixtures need to be committed. Content is stored uncompressed
(``compress="none"``) so it can be compared byte-for-byte via the shared decoder.
"""

import sqlite3
import zipfile
from pathlib import Path

import pytest

from dphe_db_pipeline.extractor.stored_content import decode_stored_content
from dphe_db_pipeline.loader.load_to_sqlite import load_files_to_db


def _stored_rows(db_path: Path) -> dict[str, tuple[bytes, str]]:
    """Return {filename: (content_bytes, encoding)} from the files table."""
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            name: (content, encoding)
            for name, content, encoding in conn.execute(
                "SELECT filename, content, encoding FROM files"
            )
        }
    finally:
        conn.close()


def test_load_directory_recursive(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "sub").mkdir(parents=True)
    (source / "a.json").write_text('{"a": 1}', encoding="utf-8")
    (source / "sub" / "b.json").write_text('{"b": 2}', encoding="utf-8")

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(str(source), str(db_path), compress="none")

    assert (loaded, errors) == (2, 0)
    rows = _stored_rows(db_path)
    # Keys are basenames only -- directory prefixes are stripped.
    assert set(rows) == {"a.json", "b.json"}
    assert decode_stored_content(*rows["a.json"]) == '{"a": 1}'
    assert decode_stored_content(*rows["b.json"]) == '{"b": 2}'


def test_load_skips_os_metadata_files(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "sub").mkdir(parents=True)
    (source / "real.json").write_text('{"r": 1}', encoding="utf-8")
    # OS/editor junk that must never be ingested.
    (source / ".DS_Store").write_bytes(b"\x00junk")
    (source / "sub" / ".DS_Store").write_bytes(b"\x00junk")
    (source / "._real.json").write_bytes(b"\x00resourcefork")

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(str(source), str(db_path), compress="none")

    assert (loaded, errors) == (1, 0)
    assert set(_stored_rows(db_path)) == {"real.json"}


def test_load_zip_skips_macosx_metadata(tmp_path: Path) -> None:
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("p1.json", '{"id": 1}')
        zf.writestr(".DS_Store", b"\x00junk".decode("latin-1"))
        zf.writestr("__MACOSX/._p1.json", b"\x00fork".decode("latin-1"))

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(
        str(tmp_path), str(db_path), zip_file=str(archive), compress="none"
    )

    assert (loaded, errors) == (1, 0)
    assert set(_stored_rows(db_path)) == {"p1.json"}


def test_load_directory_non_recursive_skips_subdirs(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "sub").mkdir(parents=True)
    (source / "top.json").write_text("top", encoding="utf-8")
    (source / "sub" / "deep.json").write_text("deep", encoding="utf-8")

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(
        str(source), str(db_path), recursive=False, compress="none"
    )

    assert (loaded, errors) == (1, 0)
    assert set(_stored_rows(db_path)) == {"top.json"}


def test_load_single_zip(tmp_path: Path) -> None:
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("p1.json", '{"id": 1}')
        zf.writestr("nested/p2.json", '{"id": 2}')

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(
        str(tmp_path), str(db_path), zip_file=str(archive), compress="none"
    )

    assert (loaded, errors) == (2, 0)
    rows = _stored_rows(db_path)
    # Keys are basenames only -- the "nested/" prefix is stripped.
    assert set(rows) == {"p1.json", "p2.json"}
    assert decode_stored_content(*rows["p2.json"]) == '{"id": 2}'


def test_load_zipdir_parallel(tmp_path: Path) -> None:
    zips = tmp_path / "zips"
    (zips / "deep").mkdir(parents=True)
    with zipfile.ZipFile(zips / "one.zip", "w") as zf:
        zf.writestr("one_a.json", "A")
        zf.writestr("one_b.json", "B")
    with zipfile.ZipFile(zips / "deep" / "two.zip", "w") as zf:
        zf.writestr("two_a.json", "C")

    db_path = tmp_path / "out.sqlite3"
    loaded, errors = load_files_to_db(
        str(tmp_path),
        str(db_path),
        zipdir=str(zips),
        num_processes=2,
        compress="none",
    )

    assert errors == 0
    assert loaded == 3
    rows = _stored_rows(db_path)
    assert set(rows) == {"one_a.json", "one_b.json", "two_a.json"}
    assert decode_stored_content(*rows["one_a.json"]) == "A"


def test_load_directory_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_files_to_db(str(tmp_path / "does-not-exist"), str(tmp_path / "out.sqlite3"))


def test_load_zip_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_files_to_db(
            str(tmp_path), str(tmp_path / "out.sqlite3"), zip_file=str(tmp_path / "missing.zip")
        )
