#!/usr/bin/env python3
"""
Import parsed concept, attribute, cancer, and tumor data into SQLite database tables.

Reads from:
- output/extraction/data/concepts_by_group.csv
- output/extraction/data/attributes_by_group.csv
- output/extraction/data/cancers_by_group.csv
- output/extraction/data/tumors_by_group.csv

Creates tables:
- concepts_by_group
- attributes_by_group
- cancers_by_group
- tumors_by_group
"""

import csv
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

BitMap: Any
try:
    from pyroaring import BitMap
    BITMAP_AVAILABLE = True
except ImportError:
    BITMAP_AVAILABLE = False
    BitMap = None

# Increase CSV field size limit to handle very large patient_ids fields
csv.field_size_limit(int(1e8))  # 100 MB limit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)-8s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DatabaseImporter:
    """Import CSV data into SQLite database."""

    def __init__(self, db_path: str = "output/databases/individual/deepphe.sqlite3"):
        """
        Initialize database importer.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self.patient_id_map: dict[str, int] = {}  # Maps patient_id (string) -> sequential_id (int)
        self.next_sequential_id = 0

    def connect(self) -> bool:
        """
        Connect to the database.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def _get_or_create_sequential_id(self, patient_id: str) -> int:
        """
        Get or create a sequential 32-bit ID for a patient ID.

        Args:
            patient_id: Original patient ID (may be large integer as string)

        Returns:
            Sequential integer ID (0-based)
        """
        if patient_id not in self.patient_id_map:
            self.patient_id_map[patient_id] = self.next_sequential_id
            self.next_sequential_id += 1
        return self.patient_id_map[patient_id]

    def _create_patient_bitmap(self, patient_ids_str: str) -> bytes:
        """
        Convert comma-separated patient IDs to serialized RoaringBitmap.

        Uses sequential IDs (0, 1, 2, ...) instead of original patient IDs
        to avoid uint32 overflow issues.

        Args:
            patient_ids_str: Comma-separated patient ID string

        Returns:
            Serialized bitmap bytes, or empty bytes if bitmap not available
        """
        if not BITMAP_AVAILABLE:
            # Fallback: return empty bytes if library not available
            return b''

        try:
            # Parse patient IDs from CSV string
            if not patient_ids_str or patient_ids_str.strip() == '':
                return BitMap().serialize()

            # Convert to sequential IDs
            patient_ids = [pid.strip() for pid in patient_ids_str.split(',') if pid.strip()]
            sequential_ids = [self._get_or_create_sequential_id(pid) for pid in patient_ids]

            # Create and serialize bitmap
            bitmap = BitMap(sequential_ids)
            return bitmap.serialize()
        except Exception as e:
            logger.warning(f"Failed to create bitmap: {e}")
            return b''

    def _create_patient_id_mapping_table(self) -> bool:
        """
        Create patient_id_mapping table to store the mapping between
        original patient IDs and sequential IDs used in bitmaps.

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()

            # Drop and recreate mapping table
            cursor.execute("DROP TABLE IF EXISTS patient_id_mapping")
            cursor.execute("""
                CREATE TABLE patient_id_mapping (
                    sequential_id INTEGER PRIMARY KEY,
                    patient_id TEXT NOT NULL UNIQUE
                )
            """)

            # Create index on patient_id for reverse lookups
            cursor.execute("""
                CREATE INDEX idx_patient_id ON patient_id_mapping(patient_id)
            """)

            # Insert all mappings
            for patient_id, sequential_id in sorted(self.patient_id_map.items(), key=lambda x: x[1]):
                cursor.execute("""
                    INSERT INTO patient_id_mapping (sequential_id, patient_id)
                    VALUES (?, ?)
                """, (sequential_id, patient_id))

            self.conn.commit()
            logger.info(f"Created patient_id_mapping table with {len(self.patient_id_map)} entries")
            logger.info(f"  Sequential IDs range: 0 to {self.next_sequential_id - 1}")
            return True

        except Exception as e:
            logger.error(f"Failed to create patient_id_mapping table: {e}")
            self.conn.rollback()
            return False
            logger.warning(f"Failed to create bitmap: {e}")
            return b''

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        """Return True when a table exists in a SQLite connection."""
        cursor = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _normalize_label(value: Any, default: str = "Unknown") -> str:
        """Normalize a grouped label value."""
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    def _create_omop_bitmap_table(
        self,
        table_name: str,
        value_column: str,
        grouped_ids: dict[str, set[int]],
        sort_numeric: bool = False,
    ) -> int:
        """
        Create one omop_* bitmap table from grouped sequential IDs.

        Returns:
            Number of rows inserted.
        """
        if not self.conn:
            logger.error("Database not connected")
            return 0

        cursor = self.conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute(
            f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {value_column} TEXT NOT NULL,
                num_patients INTEGER NOT NULL,
                patient_bitmap BLOB NOT NULL
            )
            """
        )
        cursor.execute(
            f"CREATE INDEX idx_{table_name}_{value_column} ON {table_name}({value_column})"
        )

        def sort_key(item: tuple[str, set[int]]):
            value, _ = item
            if not sort_numeric:
                return (1, value)
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                return (1, value)

        inserted = 0
        for value, seq_ids in sorted(grouped_ids.items(), key=sort_key):
            if not seq_ids:
                continue
            if BITMAP_AVAILABLE:
                bitmap_blob = BitMap(seq_ids).serialize()
            else:
                bitmap_blob = b""

            cursor.execute(
                f"""
                INSERT INTO {table_name} ({value_column}, num_patients, patient_bitmap)
                VALUES (?, ?, ?)
                """,
                (value, len(seq_ids), bitmap_blob),
            )
            inserted += 1

        return inserted

    def create_and_import_omop_tables(self, omop_db_path: Path | None) -> bool:
        """
        Build omop_* bitmap tables in the target DB using CALCULATED_* source tables.

        Args:
            omop_db_path: DB that contains CALCULATED_PATIENT_DATA and CALCULATED_DX_DATA.

        Returns:
            True if successful or skipped due missing source tables; False on failure.
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        if omop_db_path is None:
            logger.info("No --omop-database provided; skipping omop_* table import.")
            return True

        target_db_resolved = Path(self.db_path).resolve()
        source_db_resolved = omop_db_path.resolve()
        same_db = target_db_resolved == source_db_resolved

        omop_conn: sqlite3.Connection | None = None
        try:
            omop_conn = self.conn if same_db else sqlite3.connect(str(source_db_resolved))
            if not self._table_exists(omop_conn, "CALCULATED_PATIENT_DATA") or not self._table_exists(omop_conn, "CALCULATED_DX_DATA"):
                logger.warning(
                    "OMOP source tables missing in %s; skipping omop_* bitmap table creation.",
                    source_db_resolved,
                )
                return True

            if not self.patient_id_map:
                logger.warning(
                    "patient_id_map is empty; omop_* tables will be empty or skipped."
                )

            gender_groups: defaultdict[str, set[int]] = defaultdict(set)
            race_groups: defaultdict[str, set[int]] = defaultdict(set)
            ethnicity_groups: defaultdict[str, set[int]] = defaultdict(set)
            age_groups: defaultdict[str, set[int]] = defaultdict(set)
            cancer_groups: defaultdict[str, set[int]] = defaultdict(set)

            patient_rows = omop_conn.execute(
                "SELECT PERSON_ID, GENDER, RACE, ETHNICITY FROM CALCULATED_PATIENT_DATA WHERE PERSON_ID IS NOT NULL"
            )
            for person_id, gender, race, ethnicity in patient_rows:
                seq_id = self.patient_id_map.get(str(person_id))
                if seq_id is None:
                    continue
                gender_groups[self._normalize_label(gender)].add(seq_id)
                race_groups[self._normalize_label(race)].add(seq_id)
                ethnicity_groups[self._normalize_label(ethnicity)].add(seq_id)

            dx_rows = omop_conn.execute(
                "SELECT PERSON_ID, AGE_AT_DX, CANCER FROM CALCULATED_DX_DATA WHERE PERSON_ID IS NOT NULL"
            )
            for person_id, age_at_dx, cancer in dx_rows:
                seq_id = self.patient_id_map.get(str(person_id))
                if seq_id is None:
                    continue
                if age_at_dx is not None and str(age_at_dx).strip() != "":
                    age_groups[str(age_at_dx).strip()].add(seq_id)
                if cancer is not None and str(cancer).strip() != "":
                    cancer_groups[str(cancer).strip()].add(seq_id)

            age_count = self._create_omop_bitmap_table(
                "omop_age_at_dx",
                "age_at_dx",
                age_groups,
                sort_numeric=True,
            )
            gender_count = self._create_omop_bitmap_table(
                "omop_gender",
                "gender",
                gender_groups,
            )
            race_count = self._create_omop_bitmap_table(
                "omop_race",
                "race",
                race_groups,
            )
            ethnicity_count = self._create_omop_bitmap_table(
                "omop_ethnicity",
                "ethnicity",
                ethnicity_groups,
            )
            cancer_count = self._create_omop_bitmap_table(
                "omop_cancers",
                "cancer",
                cancer_groups,
            )

            self.conn.commit()
            logger.info("Created omop_* bitmap tables:")
            logger.info("  omop_age_at_dx: %d row(s)", age_count)
            logger.info("  omop_gender: %d row(s)", gender_count)
            logger.info("  omop_race: %d row(s)", race_count)
            logger.info("  omop_ethnicity: %d row(s)", ethnicity_count)
            logger.info("  omop_cancers: %d row(s)", cancer_count)
            return True
        except Exception as e:
            logger.error(f"Failed to create omop_* bitmap tables: {e}")
            self.conn.rollback()
            return False
        finally:
            if omop_conn is not None and not same_db:
                omop_conn.close()

    def drop_all_tables(self) -> bool:
        """
        Drop all existing *_by_group tables and patient_id_mapping.

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()
            tables = [
                'patient_id_mapping',
                'concepts_by_group',
                'attributes_by_group',
                'cancers_by_group',
                'tumors_by_group',
                'omop_age_at_dx',
                'omop_gender',
                'omop_race',
                'omop_ethnicity',
                'omop_cancers',
            ]

            logger.info("Dropping existing tables...")
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"  Dropped {table}")

            self.conn.commit()
            logger.info("All existing tables dropped successfully\n")
            return True

        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            self.conn.rollback()
            return False

    def read_csv(self, csv_path: Path) -> list[dict[str, Any]]:
        """
        Read CSV file into list of dictionaries.

        Args:
            csv_path: Path to CSV file

        Returns:
            List of dictionaries with CSV data
        """
        data = []
        try:
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            logger.info(f"Read {len(data)} rows from {csv_path.name}")
            return data
        except Exception as e:
            logger.error(f"Failed to read {csv_path.name}: {e}")
            return []

    def create_and_import_concepts(self, csv_path: Path) -> bool:
        """
        Create concepts_by_group table and import data.

        Args:
            csv_path: Path to concepts_by_group.csv

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()

            # Create table with bitmap column
            cursor.execute("""
                CREATE TABLE concepts_by_group (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dpheGroup TEXT NOT NULL,
                    classUri TEXT NOT NULL,
                    negated BOOLEAN NOT NULL,
                    num_patients INTEGER NOT NULL,
                    patient_bitmap BLOB NOT NULL
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX idx_concepts_dpheGroup ON concepts_by_group(dpheGroup)
            """)
            cursor.execute("""
                CREATE INDEX idx_concepts_classUri ON concepts_by_group(classUri)
            """)
            cursor.execute("""
                CREATE INDEX idx_concepts_negated ON concepts_by_group(negated)
            """)

            # Read CSV data
            data = self.read_csv(csv_path)
            if not data:
                return False

            # Insert data with bitmaps
            for row in data:
                patient_ids_str = row.get('patient_ids', '')
                bitmap_bytes = self._create_patient_bitmap(patient_ids_str)

                cursor.execute("""
                    INSERT INTO concepts_by_group
                    (dpheGroup, classUri, negated, num_patients, patient_bitmap)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    row.get('dpheGroup', ''),
                    row.get('classUri', ''),
                    row.get('negated', 'false').lower() == 'true',
                    int(row.get('num_patients', 0)),
                    bitmap_bytes
                ))

            self.conn.commit()
            logger.info(f"Successfully imported {len(data)} records into concepts_by_group table")
            return True

        except Exception as e:
            logger.error(f"Failed to import concepts data: {e}")
            self.conn.rollback()
            return False

    def create_and_import_attributes(self, csv_path: Path) -> bool:
        """
        Create attributes_by_group table and import data.

        Args:
            csv_path: Path to attributes_by_group.csv

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()

            # Create table with bitmap column
            cursor.execute("""
                CREATE TABLE attributes_by_group (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attribute_name TEXT NOT NULL,
                    classUri TEXT NOT NULL,
                    negated BOOLEAN NOT NULL,
                    uncertain BOOLEAN NOT NULL,
                    historic BOOLEAN NOT NULL,
                    num_patients INTEGER NOT NULL,
                    patient_bitmap BLOB NOT NULL
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX idx_attributes_name ON attributes_by_group(attribute_name)
            """)
            cursor.execute("""
                CREATE INDEX idx_attributes_classUri ON attributes_by_group(classUri)
            """)
            cursor.execute("""
                CREATE INDEX idx_attributes_modifiers ON attributes_by_group(negated, uncertain, historic)
            """)

            # Read CSV data
            data = self.read_csv(csv_path)
            if not data:
                return False

            # Insert data with bitmaps
            for row in data:
                patient_ids_str = row.get('patient_ids', '')
                bitmap_bytes = self._create_patient_bitmap(patient_ids_str)

                cursor.execute("""
                    INSERT INTO attributes_by_group
                    (attribute_name, classUri, negated, uncertain, historic, num_patients, patient_bitmap)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('attribute_name', ''),
                    row.get('classUri', ''),
                    row.get('negated', 'false').lower() == 'true',
                    row.get('uncertain', 'false').lower() == 'true',
                    row.get('historic', 'false').lower() == 'true',
                    int(row.get('num_patients', 0)),
                    bitmap_bytes
                ))

            self.conn.commit()
            logger.info(f"Successfully imported {len(data)} records into attributes_by_group table")
            return True

        except Exception as e:
            logger.error(f"Failed to import attributes data: {e}")
            self.conn.rollback()
            return False

    def create_and_import_cancers(self, csv_path: Path) -> bool:
        """
        Create cancers_by_group table and import data.

        Args:
            csv_path: Path to cancers_by_group.csv

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()

            # Create table with bitmap column
            cursor.execute("""
                CREATE TABLE cancers_by_group (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    classUri TEXT NOT NULL,
                    negated BOOLEAN NOT NULL,
                    uncertain BOOLEAN NOT NULL,
                    historic BOOLEAN NOT NULL,
                    num_patients INTEGER NOT NULL,
                    patient_bitmap BLOB NOT NULL
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX idx_cancers_classUri ON cancers_by_group(classUri)
            """)
            cursor.execute("""
                CREATE INDEX idx_cancers_modifiers ON cancers_by_group(negated, uncertain, historic)
            """)

            # Read CSV data
            data = self.read_csv(csv_path)
            if not data:
                return False

            # Insert data with bitmaps
            for row in data:
                patient_ids_str = row.get('patient_ids', '')
                bitmap_bytes = self._create_patient_bitmap(patient_ids_str)

                cursor.execute("""
                    INSERT INTO cancers_by_group
                    (classUri, negated, uncertain, historic, num_patients, patient_bitmap)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row.get('classUri', ''),
                    row.get('negated', 'false').lower() == 'true',
                    row.get('uncertain', 'false').lower() == 'true',
                    row.get('historic', 'false').lower() == 'true',
                    int(row.get('num_patients', 0)),
                    bitmap_bytes
                ))

            self.conn.commit()
            logger.info(f"Successfully imported {len(data)} records into cancers_by_group table")
            return True

        except Exception as e:
            logger.error(f"Failed to import cancers data: {e}")
            self.conn.rollback()
            return False

    def create_and_import_tumors(self, csv_path: Path) -> bool:
        """
        Create tumors_by_group table and import data.

        Args:
            csv_path: Path to tumors_by_group.csv

        Returns:
            True if successful, False otherwise
        """
        if not self.conn:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.conn.cursor()

            # Create table with bitmap column
            cursor.execute("""
                CREATE TABLE tumors_by_group (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    classUri TEXT NOT NULL,
                    negated BOOLEAN NOT NULL,
                    uncertain BOOLEAN NOT NULL,
                    historic BOOLEAN NOT NULL,
                    num_patients INTEGER NOT NULL,
                    patient_bitmap BLOB NOT NULL
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX idx_tumors_classUri ON tumors_by_group(classUri)
            """)
            cursor.execute("""
                CREATE INDEX idx_tumors_modifiers ON tumors_by_group(negated, uncertain, historic)
            """)

            # Read CSV data
            data = self.read_csv(csv_path)
            if not data:
                return False

            # Insert data with bitmaps
            for row in data:
                patient_ids_str = row.get('patient_ids', '')
                bitmap_bytes = self._create_patient_bitmap(patient_ids_str)

                cursor.execute("""
                    INSERT INTO tumors_by_group
                    (classUri, negated, uncertain, historic, num_patients, patient_bitmap)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row.get('classUri', ''),
                    row.get('negated', 'false').lower() == 'true',
                    row.get('uncertain', 'false').lower() == 'true',
                    row.get('historic', 'false').lower() == 'true',
                    int(row.get('num_patients', 0)),
                    bitmap_bytes
                ))

            self.conn.commit()
            logger.info(f"Successfully imported {len(data)} records into tumors_by_group table")
            return True

        except Exception as e:
            logger.error(f"Failed to import tumors data: {e}")
            self.conn.rollback()
            return False

    def import_all(self, data_dir: Path, omop_db_path: Path | None = None) -> bool:
        """
        Import all four CSV files into database tables.

        Args:
            data_dir: Path to directory containing CSV files

        Returns:
            True if all imports successful, False otherwise
        """
        logger.info("="*80)
        logger.info("IMPORTING PARSED DATA INTO DATABASE (WITH BITMAP OPTIMIZATION)")
        logger.info("="*80)
        logger.info(f"Data directory: {data_dir}")
        logger.info(f"Bitmap support: {'Enabled' if BITMAP_AVAILABLE else 'Disabled (install pyroaring)'}\n")

        if not BITMAP_AVAILABLE:
            logger.warning("pyroaring library not found. Install with: pip install pyroaring")
            logger.warning("Continuing with empty bitmaps...\n")

        csv_files = {
            'concepts': data_dir / 'concepts_by_group.csv',
            'attributes': data_dir / 'attributes_by_group.csv',
            'cancers': data_dir / 'cancers_by_group.csv',
            'tumors': data_dir / 'tumors_by_group.csv'
        }
        required_csv_names = {'concepts', 'cancers', 'tumors'}

        # Warn about missing CSVs but do not abort -- an empty extraction is valid.
        missing_names = [name for name, path in csv_files.items() if not path.exists()]
        present_files = {name: path for name, path in csv_files.items() if path.exists()}

        if missing_names:
            logger.warning(
                "The following CSV files are absent and will be skipped: %s",
                ", ".join(f"{n}_by_group.csv" for n in missing_names),
            )

        missing_required = sorted(required_csv_names.intersection(missing_names))
        if missing_required:
            logger.error(
                "Required CSV files are missing: %s",
                ", ".join(f"{n}_by_group.csv" for n in missing_required),
            )
            return False

        if not present_files:
            logger.error("No CSV files found in %s -- nothing to import.", data_dir)
            return False

        logger.info("Found %d/%d CSV file(s) to import", len(present_files), len(csv_files))
        logger.info("")

        # Drop all existing tables first
        if not self.drop_all_tables():
            return False

        # Import only the CSVs that exist
        results = {}

        if 'concepts' in present_files:
            logger.info("Importing concepts_by_group.csv...")
            results['concepts'] = self.create_and_import_concepts(csv_files['concepts'])
            logger.info("")

        if 'attributes' in present_files:
            logger.info("Importing attributes_by_group.csv...")
            results['attributes'] = self.create_and_import_attributes(csv_files['attributes'])
            logger.info("")

        if 'cancers' in present_files:
            logger.info("Importing cancers_by_group.csv...")
            results['cancers'] = self.create_and_import_cancers(csv_files['cancers'])
            logger.info("")

        if 'tumors' in present_files:
            logger.info("Importing tumors_by_group.csv...")
            results['tumors'] = self.create_and_import_tumors(csv_files['tumors'])
            logger.info("")

        # Create patient ID mapping table
        logger.info("Creating patient_id_mapping table...")
        mapping_success = self._create_patient_id_mapping_table()
        logger.info("")

        logger.info("Creating omop_* bitmap tables...")
        omop_success = self.create_and_import_omop_tables(omop_db_path)
        logger.info("")

        # Summary
        logger.info("="*80)
        logger.info("IMPORT SUMMARY")
        logger.info("="*80)
        skipped = len(missing_names)
        successful = sum(1 for v in results.values() if v)
        logger.info(f"Successfully imported: {successful}/{len(present_files)} tables (skipped {skipped})")
        for name, success in results.items():
            status = "ok" if success else "FAILED"
            logger.info(f"  [{status}] {name}_by_group")
        for name in missing_names:
            logger.info(f"  [skip] {name}_by_group (no CSV)")

        mapping_status = "ok" if mapping_success else "FAILED"
        logger.info(f"  [{mapping_status}] patient_id_mapping ({len(self.patient_id_map)} patients)")
        omop_status = "ok" if omop_success else "FAILED"
        logger.info(f"  [{omop_status}] omop_* bitmap tables")
        logger.info("="*80)

        return bool(results) and all(results.values()) and mapping_success and omop_success


def run_import(
    db_path: Path,
    data_dir: Path,
    omop_db_path: Path | None = None,
) -> bool:
    """Import grouped CSVs and OMOP bitmap tables into the target SQLite database."""
    data_dir = data_dir.resolve()
    db_path = db_path.resolve()
    omop_db_path = omop_db_path.resolve() if omop_db_path else db_path

    if not data_dir.exists():
        logger.error("Data directory not found: %s", data_dir)
        return False

    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return False
    if not omop_db_path.exists():
        logger.error("OMOP database not found: %s", omop_db_path)
        return False

    importer = DatabaseImporter(str(db_path))

    if not importer.connect():
        return False

    try:
        return importer.import_all(data_dir, omop_db_path=omop_db_path)
    finally:
        importer.disconnect()


def main() -> bool:
    """Main entry point."""
    import argparse

    from dphe_db_pipeline.paths import DEFAULT_COMPRESSED_DB, DEFAULT_EXTRACTION_DATA_DIR

    parser = argparse.ArgumentParser(
        description="Import parsed CSV data into the DeepPhe SQLite database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_COMPRESSED_DB,
        help=f"Path to the target SQLite database (default: {DEFAULT_COMPRESSED_DB}).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_EXTRACTION_DATA_DIR,
        help=f"Directory containing extracted CSV files (default: {DEFAULT_EXTRACTION_DATA_DIR}).",
    )
    parser.add_argument(
        "--omop-database",
        type=Path,
        default=None,
        help=(
            "Path to DB containing CALCULATED_* tables used to build "
            "omop_* bitmap tables (default: same as --database)."
        ),
    )
    args = parser.parse_args()

    return run_import(args.database, args.data_dir, args.omop_database)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
