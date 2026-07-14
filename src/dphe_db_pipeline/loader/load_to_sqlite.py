#!/usr/bin/env python3
"""
Script to load files from a directory into SQLite database.
Key: filename (directory prefixes stripped); timestamped DeepPhe document
     files are keyed by stable patient/document identity.
Value: file content (as bytes), optionally compressed
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
from functools import partial
from multiprocessing import Manager, Pool
from pathlib import Path
from zipfile import ZipFile

from dphe_db_pipeline.loader.compression import build_compressor, maybe_compress

logger = logging.getLogger(__name__)


def _basename(name: str) -> str:
    """Return just the file's basename, dropping any directory prefix.

    Zip entries always use forward slashes, and directory-walk keys are
    normalized to forward slashes via as_posix(), so splitting on '/' is
    correct regardless of the host OS.
    """
    return name.rsplit('/', 1)[-1]


_DEEPPHE_DOC_ID_RE = re.compile(r'^(?P<patient_id>.+)_\d{14}_D_(?P<document_number>\d+)$')
_DEEPPHE_DOC_FILENAME_RE = re.compile(
    r'^(?P<patient_id>.+)_\d{14}_D_(?P<document_number>\d+)_Doc\.json$'
)


def _extract_doc_parts(base_name: str, document: dict) -> tuple[str, str]:
    """Return patient id and document number from a timestamped DeepPhe document."""
    for candidate in (document.get('id'), base_name.removesuffix('_Doc.json')):
        match = _DEEPPHE_DOC_ID_RE.match(str(candidate or ''))
        if match:
            return match.group('patient_id'), match.group('document_number')

    match = _DEEPPHE_DOC_FILENAME_RE.match(base_name)
    return (match.group('patient_id'), match.group('document_number')) if match else ('', '')


def _escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _legacy_timestamped_doc_like(patient_id: str, document_number: str) -> str:
    escaped_patient_id = _escape_like(patient_id)
    return f'{escaped_patient_id}\\_%\\_D\\_{document_number}\\_Doc.json'


def _storage_entry(name: str, content: bytes) -> tuple[str, str]:
    """Return the SQLite key and legacy duplicate pattern for an input file.

    DeepPhe document filenames include a run timestamp, so repeated pipeline
    runs can otherwise store the same source report many times under different
    keys. For timestamped ``*_Doc.json`` rows, key by patient plus stable
    document name while leaving non-document files on their basename.
    """
    base = _basename(name)
    if not base.endswith('_Doc.json'):
        return base, ''

    try:
        document = json.loads(content.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return base, ''

    if not isinstance(document, dict):
        return base, ''

    patient_id, document_number = _extract_doc_parts(base, document)
    document_name = str(document.get('name') or '').strip()
    if not patient_id or not document_name:
        return base, ''

    stable_stem = _basename(document_name).removesuffix('.json')
    if not stable_stem:
        return base, ''

    legacy_like = (
        _legacy_timestamped_doc_like(patient_id, document_number) if document_number else ''
    )

    if stable_stem.startswith(f'{patient_id}_'):
        return f'{stable_stem.removesuffix("_Doc")}_Doc.json', legacy_like

    return f'{patient_id}_{stable_stem.removesuffix("_Doc")}_Doc.json', legacy_like

# OS/filesystem metadata files that should never be ingested as patient data.
_IGNORED_BASENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def _is_metadata_file(name: str) -> bool:
    """True for OS/editor junk files that should be skipped during loading.

    ``name`` may be a full path or zip entry (forward-slash separated).
    """
    base = _basename(name)
    if base in _IGNORED_BASENAMES:
        return True
    # macOS AppleDouble resource forks ("._foo.json").
    if base.startswith("._"):
        return True
    # macOS zip resource-fork tree.
    if name == "__MACOSX" or name.startswith("__MACOSX/") or "/__MACOSX/" in name:
        return True
    return False


def _ensure_schema(conn: sqlite3.Connection):
    """Ensure the files table exists with expected columns and indexes."""
    cur = conn.cursor()
    # Base table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS files (
            filename TEXT PRIMARY KEY,
            content BLOB NOT NULL,
            encoding TEXT NOT NULL DEFAULT 'raw'
        )
    ''')
    # Check for encoding column in case an older DB exists
    cur.execute("PRAGMA table_info(files)")
    cols = {row[1] for row in cur.fetchall()}  # row[1] is name
    if 'encoding' not in cols:
        cur.execute("ALTER TABLE files ADD COLUMN encoding TEXT NOT NULL DEFAULT 'raw'")
    # Index to speed prefix searches
    cur.execute('CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)')
    conn.commit()

def process_single_zip(zip_path, db_path, lock, compress_algo: str = 'zstd', compression_level: int = 1, min_compress_bytes: int = 512):
    """
    Process a single zip file and write directly to database.
    This function is called by each worker process.

    Args:
        zip_path: Path to the zip file to process
        db_path: Path to the SQLite database
        lock: Multiprocessing lock to serialize database writes
        compress_algo: Compression algorithm ('zstd', 'lz4', 'none/raw')
        compression_level: Compression level for the chosen algorithm
        min_compress_bytes: Only attempt to compress if content >= this many bytes

    Returns:
        tuple: (loaded_count, error_count, total_bytes, zip_name)
    """
    # Workers may run in spawned processes that do not inherit the parent's
    # logging handlers; configure a handler here if none exists (idempotent).
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    loaded_count = 0
    error_count = 0
    total_bytes = 0

    # Build compressor in this worker
    algo_name, _comp, compress_fn = build_compressor(compress_algo, compression_level)

    try:
        # Read all files from zip first (parallel processing - no lock needed)
        file_data_list = []  # tuples of (filename, content_bytes, encoding, legacy_like)
        with ZipFile(zip_path, 'r') as zf:
            # Get list of files in zip (exclude directories and OS metadata)
            file_list = [
                name for name in zf.namelist()
                if not name.endswith('/') and not _is_metadata_file(name)
            ]

            for file_name in file_list:
                try:
                    # Read file content from zip
                    value = zf.read(file_name)

                    # Optionally compress
                    store_bytes, encoding = maybe_compress(value, algo_name, compress_fn, min_compress_bytes)

                    # Store data for batch insertion.
                    storage_key, legacy_like = _storage_entry(file_name, value)
                    file_data_list.append((storage_key, store_bytes, encoding, legacy_like))

                    loaded_count += 1
                    total_bytes += len(value)

                except Exception as e:
                    logger.error("Error loading %s from %s: %s", file_name, zip_path.name, e)
                    error_count += 1

        # Acquire lock before database write (serializes writes across all processes)
        with lock:
            # Open database connection
            conn = sqlite3.connect(db_path, timeout=60.0)
            cursor = conn.cursor()

            try:
                # Ensure schema and WAL for this connection
                _ensure_schema(conn)
                cursor.execute('PRAGMA journal_mode = WAL')

                # Begin transaction for this zip file
                conn.execute('BEGIN IMMEDIATE')

                legacy_patterns = [
                    (legacy_like,)
                    for _key, _content, _encoding, legacy_like in file_data_list
                    if legacy_like
                ]
                if legacy_patterns:
                    cursor.executemany(
                        "DELETE FROM files WHERE filename LIKE ? ESCAPE '\\'",
                        legacy_patterns,
                    )

                # Batch insert all files from this zip
                cursor.executemany(
                    'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                    [
                        (storage_key, content_bytes, encoding)
                        for storage_key, content_bytes, encoding, _legacy_like in file_data_list
                    ]
                )

                # Commit transaction for this zip
                conn.commit()

                logger.info("Processed and inserted %d files from %s", loaded_count, zip_path.name)

            except Exception as e:
                logger.error("Error writing to database for %s: %s", zip_path, e)
                error_count += loaded_count  # Count all files as errors
                loaded_count = 0
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            finally:
                conn.close()

    except Exception as e:
        logger.error("Error processing zip file %s: %s", zip_path, e)
        error_count += 1

    return loaded_count, error_count, total_bytes, str(zip_path)


def load_files_to_db(
    input_dir: str,
    db_path: str,
    recursive: bool = True,
    zip_file: str | None = None,
    zipdir: str | None = None,
    num_processes: int | None = None,
    compress: str = 'zstd',
    level: int = 1,
    min_compress_bytes: int = 512,
    vacuum: bool = False,
):
    """
    Load all files from input_dir or zip file into a SQLite database.

    Args:
        input_dir: Directory containing files to load (ignored if zip_file or zipdir is provided)
        db_path: Path where SQLite database will be created/opened
        recursive: Whether to recursively scan subdirectories (default: True)
        zip_file: Path to zip file containing files to load (optional)
        zipdir: Path to directory containing zip files to process recursively (optional)
        num_processes: Number of parallel processes to use for zip processing
            (default: number of available CPUs)
        compress: Compression algorithm: zstd, lz4, none
        level: Compression level for the chosen algorithm
        min_compress_bytes: Only attempt to compress if content >= this many bytes
        vacuum: Run VACUUM at the end to shrink file size (can take time)
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Open SQLite database with optimizations for speed
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure schema
    _ensure_schema(conn)

    # Performance optimizations (sized to be helpful without being greedy on small hosts)
    cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging for better concurrency
    cursor.execute('PRAGMA synchronous = NORMAL')  # Balance between speed and safety
    cursor.execute('PRAGMA cache_size = -65536')  # 64MB cache (negative = KB)
    cursor.execute('PRAGMA temp_store = MEMORY')  # Use memory for temp storage
    cursor.execute('PRAGMA mmap_size = 268435456')  # 256MB memory-mapped I/O

    # Begin transaction for bulk insert (will be committed later)
    conn.execute('BEGIN TRANSACTION')

    # Build compressor for main thread paths
    algo_name_main, _comp_main, compress_fn_main = build_compressor(compress, level)

    # Load files into database
    loaded_count = 0
    error_count = 0
    total_bytes = 0
    total_files = 0

    if zipdir:
        # Load from all zip files in directory recursively using multiprocessing
        zipdir_path = Path(zipdir)
        if not zipdir_path.exists():
            raise ValueError(f"Zip directory does not exist: {zipdir}")

        if not zipdir_path.is_dir():
            raise ValueError(f"Zip directory path is not a directory: {zipdir}")

        # Resolve worker count from the host's CPU budget when not specified
        workers = num_processes if num_processes and num_processes > 0 else (os.cpu_count() or 4)

        # Find all zip files recursively
        zip_files = list(zipdir_path.rglob('*.zip'))
        logger.info("Found %d zip files in %s", len(zip_files), zipdir)
        logger.info("Processing with %d parallel processes...", workers)

        # Create a lock for serializing database writes
        manager = Manager()
        lock = manager.Lock()

        # Process zip files in parallel
        process_func = partial(
            process_single_zip,
            db_path=db_path,
            lock=lock,
            compress_algo=compress,
            compression_level=level,
            min_compress_bytes=min_compress_bytes,
        )

        with Pool(processes=workers) as pool:
            results = pool.map(process_func, zip_files)

        # Aggregate results (files already written to database by workers)
        logger.info("Aggregating results...")
        for zip_loaded, zip_errors, zip_bytes, _zip_name in results:
            loaded_count += zip_loaded
            error_count += zip_errors
            total_bytes += zip_bytes

        total_files = loaded_count
        logger.info("All zip files processed. Total: %d files inserted.", loaded_count)


    elif zip_file:
        # Load from single zip file
        zip_path = Path(zip_file)
        if not zip_path.exists():
            raise ValueError(f"Zip file does not exist: {zip_file}")

        logger.info("Loading files from zip: %s", zip_file)

        with ZipFile(zip_path, 'r') as zf:
            # Get list of files in zip (exclude directories and OS metadata)
            file_list = [
                name for name in zf.namelist()
                if not name.endswith('/') and not _is_metadata_file(name)
            ]
            total_files = len(file_list)
            logger.info("Found %d files in zip", total_files)

            for file_name in file_list:
                try:
                    # Read file content from zip
                    value = zf.read(file_name)

                    # Optionally compress
                    store_bytes, encoding = maybe_compress(value, algo_name_main, compress_fn_main, min_compress_bytes)

                    # Store in SQLite (will replace if key exists)
                    storage_key, legacy_like = _storage_entry(file_name, value)
                    if legacy_like:
                        cursor.execute(
                            "DELETE FROM files WHERE filename LIKE ? ESCAPE '\\'",
                            (legacy_like,),
                        )
                    cursor.execute(
                        'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                        (storage_key, store_bytes, encoding)
                    )

                    loaded_count += 1
                    total_bytes += len(value)

                    if loaded_count % 100 == 0:
                        logger.info("Loaded %d/%d files...", loaded_count, total_files)

                except Exception as e:
                    logger.error("Error loading %s: %s", file_name, e)
                    error_count += 1

        conn.commit()
    else:
        # Load from directory
        input_path = Path(input_dir)

        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_dir}")

        if not input_path.is_dir():
            raise ValueError(f"Input path is not a directory: {input_dir}")

        # Collect files to process (skip OS metadata like .DS_Store)
        if recursive:
            files = [f for f in input_path.rglob('*') if f.is_file() and not _is_metadata_file(f.name)]
        else:
            files = [f for f in input_path.glob('*') if f.is_file() and not _is_metadata_file(f.name)]

        total_files = len(files)
        logger.info("Found %d files to load", total_files)

        for file_path in files:
            try:
                # Read file content as value
                with open(file_path, 'rb') as f:
                    value = f.read()

                # Optionally compress
                store_bytes, encoding = maybe_compress(value, algo_name_main, compress_fn_main, min_compress_bytes)

                # Store in SQLite
                storage_key, legacy_like = _storage_entry(file_path.name, value)
                if legacy_like:
                    cursor.execute(
                        "DELETE FROM files WHERE filename LIKE ? ESCAPE '\\'",
                        (legacy_like,),
                    )
                cursor.execute(
                    'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                    (storage_key, store_bytes, encoding)
                )

                loaded_count += 1
                total_bytes += len(value)

                if loaded_count % 100 == 0:
                    logger.info("Loaded %d/%d files...", loaded_count, total_files)

            except Exception as e:
                logger.error("Error loading %s: %s", file_path, e)
                error_count += 1

    # Commit transaction and close database
    conn.commit()

    # Optionally VACUUM to shrink file on disk
    if vacuum:
        logger.info("Running VACUUM to compact the database file (this may take a while)...")
        conn.execute('VACUUM')
        conn.commit()

    conn.close()

    logger.info("=== Summary ===")
    logger.info("Total files found: %d", total_files)
    logger.info("Successfully loaded: %d", loaded_count)
    logger.info("Errors: %d", error_count)
    logger.info("Total bytes loaded (raw): %s", f"{total_bytes:,}")
    logger.info("Database location: %s", db_path)

    return loaded_count, error_count


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)-8s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Load files from a directory or zip file into SQLite database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load all files from a directory recursively
  python load_to_sqlite.py /path/to/files database.db

  # Load only files in the top-level directory (no recursion)
  python load_to_sqlite.py /path/to/files database.db --no-recursive

  # Load files from a zip file
  python load_to_sqlite.py database.db --zip /path/to/archive.zip

  # Load files from all zip files in a directory recursively
  python load_to_sqlite.py database.db --zipdir /path/to/zip/directory

  # Use fast compression (zstd level 1) on values >= 1KB
  python load_to_sqlite.py /path/to/files database.db --compress zstd --level 1 --min-compress-bytes 1024
        """
    )

    parser.add_argument(
        'input_dir',
        nargs='?',
        default='.',
        help='Directory containing files to load into SQLite (ignored if --zip is used)'
    )

    parser.add_argument(
        'db_path',
        help='Path where SQLite database will be created/opened'
    )

    parser.add_argument(
        '--no-recursive',
        dest='recursive',
        action='store_false',
        default=True,
        help='Do not recursively scan subdirectories (default: recursive)'
    )

    parser.add_argument(
        '--zip',
        dest='zip_file',
        help='Path to zip file containing files to load'
    )

    parser.add_argument(
        '--zipdir',
        dest='zipdir',
        help='Path to directory containing zip files to process recursively'
    )

    parser.add_argument(
        '--processes',
        dest='num_processes',
        type=int,
        default=None,
        help='Number of parallel processes when using --zipdir (default: number of CPUs)'
    )

    parser.add_argument(
        '--compress',
        choices=['zstd', 'lz4', 'none', 'raw'],
        default='zstd',
        help='Compression algorithm for content values (default: zstd)'
    )

    parser.add_argument(
        '--level',
        dest='level',
        type=int,
        default=1,
        help='Compression level (algorithm-specific, default: 1 for zstd)'
    )

    parser.add_argument(
        '--min-compress-bytes',
        dest='min_compress_bytes',
        type=int,
        default=512,
        help='Only attempt to compress values with this many bytes or more (default: 512)'
    )

    parser.add_argument(
        '--vacuum',
        action='store_true',
        help='Run VACUUM after load to compact the database file'
    )

    args = parser.parse_args()

    try:
        load_files_to_db(
            args.input_dir,
            args.db_path,
            recursive=args.recursive,
            zip_file=args.zip_file,
            zipdir=args.zipdir,
            num_processes=args.num_processes,
            compress=args.compress,
            level=args.level,
            min_compress_bytes=args.min_compress_bytes,
            vacuum=args.vacuum,
        )
    except Exception as e:
        logger.error("Error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
