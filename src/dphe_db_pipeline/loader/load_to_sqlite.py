#!/usr/bin/env python3
"""
Script to load files from a directory into SQLite database.
Key: filename (relative path from input directory)
Value: file content (as bytes), optionally compressed
"""

import argparse
import sqlite3
import sys
from functools import partial
from multiprocessing import Manager, Pool
from pathlib import Path
from zipfile import ZipFile


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


def _build_compressor(algo: str, level: int):
    """Build and return a compressor object and a callable that compresses bytes.
    Returns (algo_name, compressor, compress_fn). algo_name is 'zstd'/'lz4'/'raw'.
    """
    algo = (algo or 'zstd').lower()
    if algo == 'none' or algo == 'raw':
        return 'raw', None, (lambda b: b)
    if algo == 'zstd':
        try:
            import zstandard as zstd
        except ImportError as e:
            raise RuntimeError("zstandard package is required for --compress zstd. Install with: pip install zstandard") from e
        c = zstd.ZstdCompressor(level=level)
        return 'zstd', c, (lambda b: c.compress(b))
    if algo == 'lz4':
        try:
            import lz4.frame as lz4f
        except ImportError as e:
            raise RuntimeError("lz4 package is required for --compress lz4. Install with: pip install lz4") from e
        return 'lz4', None, (lambda b: lz4f.compress(b, compression_level=level))
    raise ValueError(f"Unsupported compression algorithm: {algo}")


def _maybe_compress(data: bytes, algo_name: str, compress_fn, min_bytes: int) -> tuple[bytes, str]:
    """Compress data if it's large enough and compression helps; returns (stored_bytes, encoding)."""
    if algo_name == 'raw':
        return data, 'raw'
    if len(data) < max(0, int(min_bytes)):
        return data, 'raw'
    try:
        comp = compress_fn(data)
        # Only keep compressed if smaller
        if len(comp) < len(data):
            return comp, algo_name
        return data, 'raw'
    except Exception:
        # On any compression failure, store raw
        return data, 'raw'


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
    loaded_count = 0
    error_count = 0
    total_bytes = 0

    # Build compressor in this worker
    algo_name, _comp, compress_fn = _build_compressor(compress_algo, compression_level)

    try:
        # Read all files from zip first (parallel processing - no lock needed)
        file_data_list = []  # tuples of (filename, content_bytes, encoding)
        with ZipFile(zip_path, 'r') as zf:
            # Get list of files in zip (exclude directories)
            file_list = [name for name in zf.namelist() if not name.endswith('/')]

            for file_name in file_list:
                try:
                    # Read file content from zip
                    value = zf.read(file_name)

                    # Optionally compress
                    store_bytes, encoding = _maybe_compress(value, algo_name, compress_fn, min_compress_bytes)

                    # Store data for batch insertion
                    file_data_list.append((file_name, store_bytes, encoding))

                    loaded_count += 1
                    total_bytes += len(value)

                except Exception as e:
                    print(f"  Error loading {file_name} from {zip_path.name}: {e}", file=sys.stderr)
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

                # Batch insert all files from this zip
                cursor.executemany(
                    'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                    file_data_list
                )

                # Commit transaction for this zip
                conn.commit()

                print(f"  Processed and inserted {loaded_count} files from {zip_path.name}")

            except Exception as e:
                print(f"Error writing to database for {zip_path}: {e}", file=sys.stderr)
                error_count += loaded_count  # Count all files as errors
                loaded_count = 0
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            finally:
                conn.close()

    except Exception as e:
        print(f"Error processing zip file {zip_path}: {e}", file=sys.stderr)
        error_count += 1

    return loaded_count, error_count, total_bytes, str(zip_path)


def load_files_to_db(
    input_dir: str,
    db_path: str,
    recursive: bool = True,
    zip_file: str | None = None,
    zipdir: str | None = None,
    num_processes: int = 12,
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
        num_processes: Number of parallel processes to use for zip processing (default: 12)
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

    # Performance optimizations
    cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging for better concurrency
    cursor.execute('PRAGMA synchronous = NORMAL')  # Balance between speed and safety
    cursor.execute('PRAGMA cache_size = -512000')  # 512MB cache (negative = KB)
    cursor.execute('PRAGMA temp_store = MEMORY')  # Use memory for temp storage
    cursor.execute('PRAGMA mmap_size = 2147483648')  # 2GB memory-mapped I/O

    # Begin transaction for bulk insert (will be committed later)
    conn.execute('BEGIN TRANSACTION')

    # Build compressor for main thread paths
    algo_name_main, _comp_main, compress_fn_main = _build_compressor(compress, level)

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

        # Find all zip files recursively
        zip_files = list(zipdir_path.rglob('*.zip'))
        print(f"Found {len(zip_files)} zip files in {zipdir}")
        print(f"Processing with {num_processes} parallel processes...")

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

        with Pool(processes=num_processes) as pool:
            results = pool.map(process_func, zip_files)

        # Aggregate results (files already written to database by workers)
        print("\nAggregating results...")
        for zip_loaded, zip_errors, zip_bytes, _zip_name in results:
            loaded_count += zip_loaded
            error_count += zip_errors
            total_bytes += zip_bytes

        total_files = loaded_count
        print(f"All zip files processed. Total: {loaded_count} files inserted.")


    elif zip_file:
        # Load from single zip file
        zip_path = Path(zip_file)
        if not zip_path.exists():
            raise ValueError(f"Zip file does not exist: {zip_file}")

        print(f"Loading files from zip: {zip_file}")

        with ZipFile(zip_path, 'r') as zf:
            # Get list of files in zip (exclude directories)
            file_list = [name for name in zf.namelist() if not name.endswith('/')]
            total_files = len(file_list)
            print(f"Found {total_files} files in zip")

            for file_name in file_list:
                try:
                    # Read file content from zip
                    value = zf.read(file_name)

                    # Optionally compress
                    store_bytes, encoding = _maybe_compress(value, algo_name_main, compress_fn_main, min_compress_bytes)

                    # Store in SQLite (will replace if key exists)
                    cursor.execute(
                        'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                        (file_name, store_bytes, encoding)
                    )

                    loaded_count += 1
                    total_bytes += len(value)

                    if loaded_count % 100 == 0:
                        print(f"Loaded {loaded_count}/{total_files} files...")

                except Exception as e:
                    print(f"Error loading {file_name}: {e}", file=sys.stderr)
                    error_count += 1

        conn.commit()
    else:
        # Load from directory
        input_path = Path(input_dir)

        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_dir}")

        if not input_path.is_dir():
            raise ValueError(f"Input path is not a directory: {input_dir}")

        # Collect files to process
        if recursive:
            files = [f for f in input_path.rglob('*') if f.is_file()]
        else:
            files = [f for f in input_path.glob('*') if f.is_file()]

        total_files = len(files)
        print(f"Found {total_files} files to load")

        for file_path in files:
            try:
                # Use relative path from input_dir as key
                relative_path = file_path.relative_to(input_path)
                key = str(relative_path)

                # Read file content as value
                with open(file_path, 'rb') as f:
                    value = f.read()

                # Optionally compress
                store_bytes, encoding = _maybe_compress(value, algo_name_main, compress_fn_main, min_compress_bytes)

                # Store in SQLite
                cursor.execute(
                    'INSERT OR REPLACE INTO files (filename, content, encoding) VALUES (?, ?, ?)',
                    (key, store_bytes, encoding)
                )

                loaded_count += 1
                total_bytes += len(value)

                if loaded_count % 100 == 0:
                    print(f"Loaded {loaded_count}/{total_files} files...")

            except Exception as e:
                print(f"Error loading {file_path}: {e}", file=sys.stderr)
                error_count += 1

    # Commit transaction and close database
    conn.commit()

    # Optionally VACUUM to shrink file on disk
    if vacuum:
        print("Running VACUUM to compact the database file (this may take a while)...")
        conn.execute('VACUUM')
        conn.commit()

    conn.close()

    print("\n=== Summary ===")
    print(f"Total files found: {total_files}")
    print(f"Successfully loaded: {loaded_count}")
    print(f"Errors: {error_count}")
    print(f"Total bytes loaded (raw): {total_bytes:,}")
    print(f"Database location: {db_path}")

    return loaded_count, error_count


def main():
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
        default=12,
        help='Number of parallel processes when using --zipdir (default: 12)'
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
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
