#!/usr/bin/env python3
"""
Script to query and verify files in a SQLite database.
"""

import sys
import argparse
import sqlite3


def open_db(db_path: str):
    """Open database with proper options optimized for reads."""
    conn = sqlite3.connect(db_path)
    # Set pragmas for optimal read performance
    conn.execute('PRAGMA cache_size = -512000')  # 512MB cache
    conn.execute('PRAGMA mmap_size = 2147483648')  # 2GB memory-mapped I/O
    conn.execute('PRAGMA temp_store = MEMORY')
    return conn


def query_prefix(db_path: str, prefix_str: str, limit: int = 10, show_values: bool = False):
    """Query all keys that start with the given prefix."""
    conn = open_db(db_path)
    cursor = conn.cursor()

    # Use LIKE with ESCAPE for prefix matching
    # Need to escape % and _ characters in the prefix
    escaped_prefix = prefix_str.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    cursor.execute(
        'SELECT filename, content FROM files WHERE filename LIKE ? ESCAPE "\\" ORDER BY filename LIMIT ?',
        (escaped_prefix + '%', limit if limit else -1)
    )

    count = 0
    for filename, content in cursor:
        print(filename)

        if show_values:
            try:
                preview = content[:100].decode('utf-8')
            except Exception:
                preview = "(Binary content)"
            print(f"  Size: {len(content)} bytes")
            print(f"  Preview: {preview}...\n")

        count += 1

    if count == 0:
        print(f"No keys found with prefix '{prefix_str}'")
    elif limit and count >= limit:
        print(f"\n... (showing first {limit} keys)")

    conn.close()


def list_keys(db_path: str, limit: int = 10):
    """List keys stored in the SQLite database."""
    conn = open_db(db_path)
    cursor = conn.cursor()

    print("Keys in database:")
    print("-" * 50)

    cursor.execute(
        'SELECT filename FROM files ORDER BY filename LIMIT ?',
        (limit if limit else -1,)
    )

    count = 0
    for (filename,) in cursor:
        print(filename)
        count += 1

    if limit and count >= limit:
        print(f"\n... (showing first {limit} keys, use --limit to see more)")

    # Get total count
    cursor.execute('SELECT COUNT(*) FROM files')
    total = cursor.fetchone()[0]
    print(f"\nTotal keys: {total}")

    conn.close()


def get_file(db_path: str, filename: str, output_path: str = None):
    """Retrieve a file from the SQLite database."""
    conn = open_db(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT content FROM files WHERE filename = ?', (filename,))
    row = cursor.fetchone()

    if row is None:
        print(f"File not found: {filename}")
        conn.close()
        return False

    value = row[0]

    if output_path:
        with open(output_path, 'wb') as f:
            f.write(value)
        print(f"File extracted to: {output_path}")
    else:
        print(f"File found: {filename}")
        print(f"Size: {len(value)} bytes")
        print("\nContent preview:")
        print("-" * 50)
        try:
            # Try to display as text
            preview = value[:500].decode('utf-8')
            print(preview)
            if len(value) > 500:
                print("\n... (truncated)")
        except UnicodeDecodeError:
            print("(Binary content - cannot display as text)")

    conn.close()
    return True


def count_keys(db_path: str):
    """Count total number of keys in the database."""
    conn = open_db(db_path)
    cursor = conn.cursor()

    # Get total count
    cursor.execute('SELECT COUNT(*) FROM files')
    count = cursor.fetchone()[0]

    print(f"Total keys in database: {count}")

    # Get last 10 key/value pairs
    cursor.execute(
        'SELECT filename, content FROM files ORDER BY filename DESC LIMIT 10'
    )

    last_10 = cursor.fetchall()

    if last_10:
        # Reverse to show in ascending order
        last_10.reverse()
        print(f"\nLast {len(last_10)} key/value pairs:")
        print("-" * 50)
        for filename, content in last_10:
            print(f"Key: {filename}")
            print(f"  Size: {len(content)} bytes")

            # Try to show a preview of the value
            try:
                preview = content[:100].decode('utf-8')
                print(f"  Preview: {preview}...")
            except:
                print(f"  (Binary content)")
            print()

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Query and verify SQLite database contents"
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List keys in the database')
    list_parser.add_argument('db_path', help='Path to SQLite database')
    list_parser.add_argument('--limit', type=int, default=10,
                             help='Maximum number of keys to display (0 for all)')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get a file from the database')
    get_parser.add_argument('db_path', help='Path to SQLite database')
    get_parser.add_argument('filename', help='Filename (key) to retrieve')
    get_parser.add_argument('-o', '--output', help='Output path to save the file')

    # Count command
    count_parser = subparsers.add_parser('count', help='Count total keys in database')
    count_parser.add_argument('db_path', help='Path to SQLite database')

    # Prefix command
    prefix_parser = subparsers.add_parser('prefix', help='Query keys by prefix')
    prefix_parser.add_argument('db_path', help='Path to SQLite database')
    prefix_parser.add_argument('prefix', help='Prefix to search for')
    prefix_parser.add_argument('--limit', type=int, default=10,
                               help='Maximum number of keys to display (0 for all)')
    prefix_parser.add_argument('--show-values', action='store_true',
                               help='Show value previews')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'list':
            list_keys(args.db_path, args.limit)
        elif args.command == 'get':
            get_file(args.db_path, args.filename, args.output)
        elif args.command == 'count':
            count_keys(args.db_path)
        elif args.command == 'prefix':
            query_prefix(args.db_path, args.prefix, args.limit, args.show_values)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

