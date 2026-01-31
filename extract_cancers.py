#!/usr/bin/env python3
"""
Script to extract JSON content from the 'files' table where filenames end with '_Cancers'.
"""

import sqlite3
import json
import os
from datetime import datetime

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    print("Note: zstandard library not available. Install with: pip install zstandard")


def extract_cancers_content(db_path, output_dir="extracted_cancers"):
    """
    Extract all content from files table where filename ends with '_Cancers'.

    Args:
        db_path: Path to the SQLite database
        output_dir: Directory to save extracted JSON files
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✓ Created output directory: {output_dir}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if files table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    if not cursor.fetchone():
        print("ERROR: 'files' table not found in database!")
        conn.close()
        return

    # Get schema info
    print("\n" + "="*60)
    print("Files table schema:")
    print("="*60)
    cursor.execute("PRAGMA table_info(files)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    for col in columns:
        print(f"  {col[1]} ({col[2]})")

    # Extract content from files ending with _Cancers
    print("\n" + "="*60)
    print("Extracting content from files ending with '_Cancers'...")
    print("="*60)

    # Query for files ending with _Cancers
    query = "SELECT * FROM files WHERE filename LIKE '%_Cancers.json'"
    cursor.execute(query)

    rows = cursor.fetchall()

    if not rows:
        print("No files found ending with '_Cancers'")
        conn.close()
        return

    print(f"Found {len(rows)} file(s) ending with '_Cancers'\n")

    # Find the content column index
    try:
        content_idx = column_names.index('content')
        filename_idx = column_names.index('filename')
        encoding_idx = column_names.index('encoding') if 'encoding' in column_names else None
    except ValueError as e:
        print(f"ERROR: Required column not found: {e}")
        print(f"Available columns: {column_names}")
        conn.close()
        return

    if encoding_idx is not None:
        print(f"✓ Found 'encoding' column - will use it to decode content")

    all_cancers = []

    for idx, row in enumerate(rows, 1):
        filename = row[filename_idx]
        content = row[content_idx]
        encoding = row[encoding_idx] if encoding_idx is not None else 'utf-8'

        # Default to utf-8 if encoding is None or empty
        if not encoding:
            encoding = 'utf-8'

        print(f"\n{idx}. Processing: {filename}")
        print("   " + "-"*56)
        print(f"   Encoding: {encoding}")

        # Try to parse content as JSON
        try:
            if content:
                # Handle zstd compression
                if encoding and encoding.lower() == 'zstd':
                    if not ZSTD_AVAILABLE:
                        print(f"   ✗ zstandard library not installed. Run: pip install zstandard")
                        continue

                    if isinstance(content, bytes):
                        # Decompress zstd content
                        dctx = zstd.ZstdDecompressor()
                        decompressed = dctx.decompress(content)
                        content_str = decompressed.decode('utf-8')
                    else:
                        print(f"   ⚠ Content is not bytes, but encoding is zstd")
                        content_str = content
                else:
                    # Decode content if it's bytes using the specified encoding
                    if isinstance(content, bytes):
                        content_str = content.decode(encoding)
                    else:
                        content_str = content

                json_content = json.loads(content_str)
                all_cancers.append({
                    'filename': filename,
                    'content': json_content
                })

                # Save individual file
                safe_filename = filename.replace('/', '_').replace('\\', '_')
                # Remove .json extension if it already exists to avoid double extension
                if safe_filename.endswith('.json'):
                    safe_filename = safe_filename[:-5]
                output_file = os.path.join(output_dir, f"{safe_filename}.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(json_content, f, indent=2, ensure_ascii=False)

                print(f"   ✓ Saved to: {output_file}")
                print(f"   Content type: {type(json_content).__name__}")

                # Show preview
                if isinstance(json_content, dict):
                    print(f"   Keys: {list(json_content.keys())[:5]}")
                elif isinstance(json_content, list):
                    print(f"   Items: {len(json_content)}")
                    if json_content and isinstance(json_content[0], dict):
                        print(f"   First item keys: {list(json_content[0].keys())[:5]}")
            else:
                print("   ⚠ Content is empty/null")

        except UnicodeDecodeError as e:
            print(f"   ⚠ Error decoding with encoding '{encoding}': {e}")
            print(f"   Trying common encodings...")
            # Try common encodings as fallback
            for fallback_encoding in ['latin-1', 'iso-8859-1', 'cp1252', 'utf-16']:
                try:
                    if isinstance(content, bytes):
                        content_str = content.decode(fallback_encoding)
                        json_content = json.loads(content_str)
                        print(f"   ✓ Successfully decoded with {fallback_encoding}")

                        all_cancers.append({
                            'filename': filename,
                            'content': json_content
                        })

                        safe_filename = filename.replace('/', '_').replace('\\', '_')
                        # Remove .json extension if it already exists to avoid double extension
                        if safe_filename.endswith('.json'):
                            safe_filename = safe_filename[:-5]
                        output_file = os.path.join(output_dir, f"{safe_filename}.json")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(json_content, f, indent=2, ensure_ascii=False)
                        print(f"   ✓ Saved to: {output_file}")
                        break
                except:
                    continue
            else:
                print(f"   ✗ Could not decode content with any common encoding")
        except json.JSONDecodeError as e:
            print(f"   ⚠ Content is not valid JSON: {e}")
            print(f"   Content preview: {str(content)[:100] if content else 'None'}...")
        except Exception as e:
            print(f"   ⚠ Error processing content: {e}")

    # Save all cancers in a single file
    if all_cancers:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_file = os.path.join(output_dir, f"all_cancers_{timestamp}.json")
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(all_cancers, f, indent=2, ensure_ascii=False)

        print("\n" + "="*60)
        print(f"✓ Saved all cancers to: {combined_file}")
        print(f"✓ Total files processed: {len(all_cancers)}")
        print("="*60)

    conn.close()
    print("\n✓ Database connection closed.")
    return all_cancers


def main():
    """Main function."""
    db_path = "deepphe_100"

    if not os.path.exists(db_path):
        print(f"ERROR: Database file '{db_path}' not found!")
        return

    print(f"Connecting to database: {db_path}")

    cancers = extract_cancers_content(db_path)

    if cancers:
        print(f"\nSuccessfully extracted {len(cancers)} cancer file(s)!")
    else:
        print("\nNo cancers extracted.")


if __name__ == "__main__":
    main()

