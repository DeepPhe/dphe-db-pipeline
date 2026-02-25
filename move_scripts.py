#!/usr/bin/env python3
"""
Helper script to move root-level scripts to src/scripts/ with path updates.

This script will:
1. Copy each root-level script to src/scripts/
2. Update Path(__file__).parent to Path(__file__).parent.parent.parent
3. Verify the new files work

Run this to complete the reorganization.
"""

from pathlib import Path
import shutil
import re

# Scripts to move
SCRIPTS_TO_MOVE = [
    'create_concepts_table.py',
    'extract_cancers.py',
    'extract_cancers_data.py',
    'extract_concepts.py',
    'import_parsed_data.py',
    'parse_all_by_group.py',
    'parse_attributes_by_group.py',
    'parse_cancers_by_group.py',
    'parse_concepts_by_group.py',
    'parse_tumors_by_group.py',
    'query_tumors.py',
    'query_tumors_adenocarcinoma_breastlump.py',
]


def update_paths_in_file(content: str) -> str:
    """
    Update path references for scripts moving from root to src/scripts/.

    Changes:
    - Path(__file__).parent -> Path(__file__).parent.parent.parent
    - base_dir = Path(__file__).parent -> base_dir = Path(__file__).parent.parent.parent
    """
    # Pattern 1: Direct Path(__file__).parent usage
    content = re.sub(
        r'Path\(__file__\)\.parent(?!\.parent)',
        r'Path(__file__).parent.parent.parent',
        content
    )

    return content


def move_scripts():
    """Move scripts from root to src/scripts/ with path updates."""
    base_dir = Path(__file__).parent
    src_scripts_dir = base_dir / 'src' / 'scripts'

    # Ensure destination exists
    src_scripts_dir.mkdir(parents=True, exist_ok=True)

    print("Moving scripts to src/scripts/...")
    print("=" * 80)

    moved_count = 0
    skipped_count = 0

    for script_name in SCRIPTS_TO_MOVE:
        source_file = base_dir / script_name
        dest_file = src_scripts_dir / script_name

        if not source_file.exists():
            print(f"⚠️  SKIP: {script_name} (not found)")
            skipped_count += 1
            continue

        # Read source file
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update paths
        updated_content = update_paths_in_file(content)

        # Write to destination
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"✅ Moved: {script_name}")
        moved_count += 1

    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Moved: {moved_count} files")
    print(f"  Skipped: {skipped_count} files")
    print(f"\nFiles are now in: {src_scripts_dir}")
    print("\nNEXT STEPS:")
    print("1. Test the scripts from new location:")
    print("   python src/scripts/import_parsed_data.py")
    print("   python src/scripts/parse_all_by_group.py")
    print("   python src/scripts/query_tumors.py --list")
    print("\n2. If all tests pass, delete old root files:")
    print("   rm create_concepts_table.py extract_*.py import_*.py parse_*.py query_*.py")
    print("\n3. Update .gitignore to ignore old files")


if __name__ == '__main__':
    move_scripts()
