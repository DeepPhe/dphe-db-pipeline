#!/usr/bin/env python3
"""
Recompress existing rows in the SQLite DB to save space, then VACUUM.
This lets you shrink a large DB (e.g., 150G -> ~100G) without full reload.
Usage:
  python compact_sqlite.py db.sqlite --compress zstd --level 1 --min-compress-bytes 512 --batch 5000 --vacuum
"""
import argparse
import sqlite3


def _build_compressor(algo: str, level: int):
    algo = (algo or 'zstd').lower()
    if algo in ('none', 'raw'):
        return 'raw', (lambda b: b)
    if algo == 'zstd':
        import zstandard as zstd
        c = zstd.ZstdCompressor(level=level)
        return 'zstd', (lambda b: c.compress(b))
    if algo == 'lz4':
        import lz4.frame as lz4f
        return 'lz4', (lambda b: lz4f.compress(b, compression_level=level))
    raise ValueError(f'Unsupported algo {algo}')


def _maybe_compress(data: bytes, algo_name: str, compress_fn, min_bytes: int) -> tuple[bytes, str]:
    if algo_name == 'raw' or len(data) < min_bytes:
        return data, 'raw'
    comp = compress_fn(data)
    if len(comp) < len(data):
        return comp, algo_name
    return data, 'raw'


def main():
    ap = argparse.ArgumentParser(description='Recompress rows in SQLite files table to save space')
    ap.add_argument('db', help='Path to SQLite database')
    ap.add_argument('--compress', choices=['zstd', 'lz4', 'none', 'raw'], default='zstd')
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--min-compress-bytes', type=int, default=512)
    ap.add_argument('--batch', type=int, default=5000, help='Rows per transaction')
    ap.add_argument('--vacuum', action='store_true')
    args = ap.parse_args()

    algo, comp_fn = _build_compressor(args.compress, args.level)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Ensure encoding column exists
    cur.execute('PRAGMA table_info(files)')
    cols = {row[1] for row in cur.fetchall()}
    if 'encoding' not in cols:
        cur.execute("ALTER TABLE files ADD COLUMN encoding TEXT NOT NULL DEFAULT 'raw'")
        conn.commit()

    cur.execute('PRAGMA journal_mode = WAL')

    processed = 0
    updated = 0
    skipped = 0

    # Iterate rows in filename order for stable progress
    cur2 = conn.cursor()
    cur2.execute('SELECT filename, content, encoding FROM files ORDER BY filename')

    batch = []
    for row in cur2:
        fname, content, enc = row
        processed += 1
        # Skip if already compressed with same algo
        if enc and enc.lower() == algo:
            skipped += 1
            continue
        # Decompress if necessary
        if enc and enc.lower() == 'zstd':
            import zstandard as zstd
            content = zstd.ZstdDecompressor().decompress(content)
        elif enc and enc.lower() == 'lz4':
            import lz4.frame as lz4f
            content = lz4f.decompress(content)
        # Try new compression
        new_bytes, new_enc = _maybe_compress(content, algo, comp_fn, args.min_compress_bytes)
        # Only write if it changes size or encoding
        if new_enc != enc or new_bytes != content:
            batch.append((new_bytes, new_enc, fname))
            updated += 1
        else:
            skipped += 1

        if len(batch) >= args.batch:
            conn.execute('BEGIN IMMEDIATE')
            cur.executemany('UPDATE files SET content = ?, encoding = ? WHERE filename = ?', batch)
            conn.commit()
            print(f"Updated {updated} / Processed {processed} (skipped {skipped})")
            batch.clear()

    if batch:
        conn.execute('BEGIN IMMEDIATE')
        cur.executemany('UPDATE files SET content = ?, encoding = ? WHERE filename = ?', batch)
        conn.commit()
        print(f"Updated {updated} / Processed {processed} (skipped {skipped})")

    if args.vacuum:
        print('Running VACUUM...')
        conn.execute('VACUUM')
        conn.commit()

    conn.close()
    print('Done')


if __name__ == '__main__':
    main()

