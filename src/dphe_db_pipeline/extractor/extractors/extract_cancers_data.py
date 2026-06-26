#!/usr/bin/env python3
"""
Extract cancer and concept data directly from the DeepPhe SQLite database.

Reads _Cancers.json and _Concepts.json files from the database 'files' table
and exports processed data to CSV files.

Output files:
- extracted_tumors.csv: One row per tumor with tumor-level attributes
- extracted_attributes.csv: One row per attribute instance across all levels
- extracted_cancers.csv: One row per top-level cancer/lesion
- extracted_concepts.csv: One row per unique concept with patient linkage
"""

import csv
import json
import logging
import queue
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from typing import Any, NamedTuple

from dphe_db_pipeline.extractor.stored_content import decode_stored_content

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)-8s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ConceptInfo(NamedTuple):
    """Container for concept information."""
    dpheGroup: str
    preferredText: str
    classUri: str
    negated: bool
    uncertain: bool
    historic: bool
    confidence: int


class DatabaseReader:
    """Read JSON files from the DeepPhe SQLite database."""

    def __init__(self, db_path: str = "output/databases/individual/deepphe.sqlite3"):
        """
        Initialize database reader.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

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

    def get_cancer_files(
        self,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        """
        Get cancer JSON files from database in chunks.

        Args:
            limit: Maximum number of files to retrieve (None for all)
            chunk_size: Number of rows to fetch at a time (default 1000)

        Returns:
            Generator yielding dictionaries of patient_id -> parsed JSON content
        """
        if not self.conn:
            raise RuntimeError("Database not connected")

        logger.info("Executing query to retrieve cancer files from database...")
        cursor = self.conn.cursor()
        query = "SELECT filename, content, encoding FROM files WHERE filename LIKE '%_Cancers.json'"

        cursor.execute(query)
        total_files = 0
        success_count = 0
        error_count = 0
        chunk_num = 0

        while True:
            chunk_num += 1
            logger.info(f"Fetching chunk {chunk_num} ({chunk_size} rows)...")
            rows = cursor.fetchmany(chunk_size)

            if not rows:
                logger.info("All files retrieved from database")
                break

            cancer_files: dict[str, Any] = {}
            total_files += len(rows)

            if limit and total_files > limit:
                rows = rows[:limit - (total_files - len(rows))]
                logger.info(f"Reached limit of {limit} files, stopping retrieval")

            for filename, content, encoding in rows:
                try:
                    # Extract patient_id from the file's basename, ignoring any
                    # directory prefix (e.g. "fake_patient1/fake_patient1_Cancers.json").
                    patient_id = Path(filename).name.replace('_Cancers.json', '').replace('.json', '')

                    # Decompress/decode content
                    content_str = decode_stored_content(content, encoding)

                    # Parse JSON
                    json_content = json.loads(content_str)

                    cancer_files[patient_id] = json_content
                    success_count += 1

                except Exception as e:
                    logger.warning(f"Skipped {filename}: {str(e)[:100]}")
                    error_count += 1

            logger.info(f"Chunk {chunk_num} complete: {len(cancer_files)} loaded, {len(rows)-len(cancer_files)} skipped")
            yield cancer_files

            if limit and total_files >= limit:
                logger.info(f"Cancer file loading complete: {success_count} succeeded, {error_count} skipped")
                break

        if not limit:
            logger.info(f"Cancer file loading complete: {success_count} succeeded, {error_count} skipped")

    def get_concept_files(
        self,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        """
        Get concept JSON files from database in chunks.

        Args:
            limit: Maximum number of files to retrieve (None for all)
            chunk_size: Number of rows to fetch at a time (default 1000)

        Returns:
            Generator yielding dictionaries of patient_id -> parsed JSON content
        """
        if not self.conn:
            raise RuntimeError("Database not connected")

        logger.info("Executing query to retrieve concept files from database...")
        cursor = self.conn.cursor()
        query = "SELECT filename, content, encoding FROM files WHERE filename LIKE '%_Concepts.json' AND filename NOT LIKE 'all_concepts_%'"

        cursor.execute(query)
        total_files = 0
        success_count = 0
        error_count = 0
        chunk_num = 0

        while True:
            chunk_num += 1
            logger.info(f"Fetching chunk {chunk_num} ({chunk_size} rows)...")
            rows = cursor.fetchmany(chunk_size)

            if not rows:
                logger.info("All files retrieved from database")
                break

            concept_files: dict[str, Any] = {}
            total_files += len(rows)

            if limit and total_files > limit:
                rows = rows[:limit - (total_files - len(rows))]
                logger.info(f"Reached limit of {limit} files, stopping retrieval")

            for filename, content, encoding in rows:
                try:
                    # Extract patient_id from the file's basename, ignoring any
                    # directory prefix (e.g. "fake_patient1/fake_patient1_Concepts.json").
                    patient_id = Path(filename).name.replace('_Concepts.json', '').replace('.json', '')

                    # Decompress/decode content
                    content_str = decode_stored_content(content, encoding)

                    # Parse JSON
                    json_content = json.loads(content_str)

                    concept_files[patient_id] = json_content
                    success_count += 1

                except Exception as e:
                    logger.warning(f"Skipped {filename}: {str(e)[:100]}")
                    error_count += 1

            logger.info(f"Chunk {chunk_num} complete: {len(concept_files)} loaded, {len(rows)-len(concept_files)} skipped")
            yield concept_files

            if limit and total_files >= limit:
                logger.info(f"Concept file loading complete: {success_count} succeeded, {error_count} skipped")
                break

        if not limit:
            logger.info(f"Concept file loading complete: {success_count} succeeded, {error_count} skipped")


class CancerDataExtractor:
    """Extract and process cancer data from parsed JSON data."""

    def __init__(self, output_dir: Path, patients_per_file: int = 1000):
        """
        Initialize the extractor.

        Args:
            output_dir: Directory for output CSV files
            patients_per_file: Number of patients per output file (default 1000)
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.patients_per_file = patients_per_file

        self.tumors_data: list[dict[str, Any]] = []
        self.attributes_data: list[dict[str, Any]] = []
        self.cancers_data: list[dict[str, Any]] = []

        # Track unique patients in order
        self.patient_order: list[str] = []
        self.patient_set: set = set()

        # Track current file number and last written file
        self.current_file_num = 1
        self.last_written_file_num = 0

    def extract_from_data(self, data: Any, patient_id: str) -> None:
        """
        Extract data from parsed cancer JSON data.

        Args:
            data: Parsed cancer JSON data (should be list of cancers)
            patient_id: Patient ID
        """

        if not isinstance(data, list):
            logger.warning(f"Expected list, got {type(data).__name__}")
            return

        # Track patient order and check if we need to write
        patient_is_new = patient_id not in self.patient_set
        if patient_is_new:
            self.patient_order.append(patient_id)
            self.patient_set.add(patient_id)

            # Check if we've reached another 1000 patients - write CSV files
            if len(self.patient_order) % self.patients_per_file == 0:
                self._write_csv_files()
                logger.info(f"✓ Wrote CSV files for patients 1-{len(self.patient_order)}")

        # Process each cancer in the data
        for cancer_idx, cancer in enumerate(data):
            # Extract top-level cancer data
            self._extract_cancer(cancer, patient_id, cancer_idx)

            # Extract tumor data
            if 'tumors' in cancer:
                for tumor_idx, tumor in enumerate(cancer['tumors']):
                    self._extract_tumor(tumor, patient_id, cancer_idx, tumor_idx)

                    # Extract tumor-level attributes
                    if 'attributes' in tumor:
                        for attr_idx, attr in enumerate(tumor['attributes']):
                            self._extract_attribute(attr, patient_id, cancer_idx, tumor_idx, 'tumor', attr_idx)

            # Extract cancer-level attributes
            if 'attributes' in cancer:
                for attr_idx, attr in enumerate(cancer['attributes']):
                    self._extract_attribute(attr, patient_id, cancer_idx, None, 'cancer', attr_idx)

    def _extract_cancer(self, cancer: dict[str, Any], patient_id: str, cancer_idx: int) -> None:
        """Extract top-level cancer data."""
        record = {
            'patient_id': patient_id,
            'cancer_index': cancer_idx,
            'cancer_id': cancer.get('id', ''),
            'classUri': cancer.get('classUri', ''),
            'negated': cancer.get('negated', False),
            'uncertain': cancer.get('uncertain', False),
            'historic': cancer.get('historic', False),
            'confidence': cancer.get('confidence', ''),
        }
        self.cancers_data.append(record)

    # ...existing code...

    def _write_csv_files(self) -> None:
        """Write accumulated data to CSV files for current patient group."""
        if not self.tumors_data and not self.attributes_data and not self.cancers_data:
            return

        # Calculate which file number this batch belongs to
        file_num = (len(self.patient_order) // self.patients_per_file)

        # Create subdirectories
        tumors_dir = self.output_dir / 'extracted_tumors'
        attributes_dir = self.output_dir / 'extracted_attributes'
        cancers_dir = self.output_dir / 'extracted_cancers'

        tumors_dir.mkdir(parents=True, exist_ok=True)
        attributes_dir.mkdir(parents=True, exist_ok=True)
        cancers_dir.mkdir(parents=True, exist_ok=True)

        # Write tumors
        if self.tumors_data:
            tumors_file = tumors_dir / f'extracted_tumors_{file_num}.csv'
            with open(tumors_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.tumors_data[0].keys())
                writer.writeheader()
                writer.writerows(self.tumors_data)
            logger.info(f"  Wrote {len(self.tumors_data)} tumor records to extracted_tumors/{tumors_file.name}")

        # Write attributes
        if self.attributes_data:
            attributes_file = attributes_dir / f'extracted_attributes_{file_num}.csv'
            with open(attributes_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.attributes_data[0].keys())
                writer.writeheader()
                writer.writerows(self.attributes_data)
            logger.info(f"  Wrote {len(self.attributes_data)} attribute records to extracted_attributes/{attributes_file.name}")

        # Write cancers
        if self.cancers_data:
            cancers_file = cancers_dir / f'extracted_cancers_{file_num}.csv'
            with open(cancers_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.cancers_data[0].keys())
                writer.writeheader()
                writer.writerows(self.cancers_data)
            logger.info(f"  Wrote {len(self.cancers_data)} cancer records to extracted_cancers/{cancers_file.name}")

        # Clear accumulated data for next batch
        self.tumors_data = []
        self.attributes_data = []
        self.cancers_data = []
        self.last_written_file_num = file_num

    def _extract_tumor(self, tumor: dict[str, Any], patient_id: str, cancer_idx: int, tumor_idx: int) -> None:
        """Extract tumor-level data."""
        concept_ids = tumor.get('conceptIds', [])
        concept_ids_str = '|'.join(concept_ids) if concept_ids else ''

        record = {
            'patient_id': patient_id,
            'cancer_index': cancer_idx,
            'tumor_index': tumor_idx,
            'tumor_id': tumor.get('id', ''),
            'classUri': tumor.get('classUri', ''),
            'conceptIds': concept_ids_str,
            'negated': tumor.get('negated', False),
            'uncertain': tumor.get('uncertain', False),
            'historic': tumor.get('historic', False),
            'confidence': tumor.get('confidence', ''),
        }
        self.tumors_data.append(record)

    def _extract_attribute(self, attr: dict[str, Any], patient_id: str, cancer_idx: int,
                          tumor_idx: Any, level: str, attr_idx: int) -> None:
        """Extract attribute values."""
        attr_name = attr.get('name', '')
        attr_id = attr.get('id', '')
        values = attr.get('values', [])

        for value_obj in values:
            record = {
                'patient_id': patient_id,
                'cancer_index': cancer_idx,
                'tumor_index': tumor_idx if level == 'tumor' else '',
                'level': level,
                'attribute_name': attr_name,
                'attribute_id': attr_id,
                'classUri': value_obj.get('classUri', ''),
                'value_id': value_obj.get('id', ''),
                'negated': value_obj.get('negated', False),
                'uncertain': value_obj.get('uncertain', False),
                'historic': value_obj.get('historic', False),
                'confidence': value_obj.get('confidence', ''),
            }
            self.attributes_data.append(record)

    def save_to_csv(self) -> None:
        """Save any remaining extracted data to CSV files."""
        # Write remaining data if any
        if self.tumors_data or self.attributes_data or self.cancers_data:
            logger.info(f"Writing remaining cancer data for patients {self.last_written_file_num * self.patients_per_file + 1}-{len(self.patient_order)}...")
            self._write_csv_files()
            logger.info("✓ Final cancer data written")


class ConceptExtractor:
    """Extract and process concept data from parsed JSON data."""

    def __init__(self, output_dir: Path, patients_per_file: int = 1000):
        """
        Initialize the extractor.

        Args:
            output_dir: Directory for output CSV file
            patients_per_file: Number of patients per output file (default 1000)
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.patients_per_file = patients_per_file
        self.concepts_data: list[dict[str, Any]] = []

        # Track unique patients in order
        self.patient_order: list[str] = []
        self.patient_set: set = set()

        # Track current file number and last written file
        self.current_file_num = 1
        self.last_written_file_num = 0

    def extract_from_data(self, data: Any, patient_id: str) -> None:
        """
        Extract data from parsed concepts JSON data.

        Args:
            data: Parsed concepts JSON data (should be dict with 'concepts' key)
            patient_id: Patient ID
        """

        # Track patient order and check if we need to write
        patient_is_new = patient_id not in self.patient_set
        if patient_is_new:
            self.patient_order.append(patient_id)
            self.patient_set.add(patient_id)

            # Check if we've reached another 1000 patients - write CSV files
            if len(self.patient_order) % self.patients_per_file == 0:
                self._write_csv_files()
                logger.info(f"✓ Wrote CSV files for patients 1-{len(self.patient_order)}")

        concepts = data.get('concepts', [])

        for concept in concepts:
            dphe_group = concept.get('dpheGroup')
            preferred_text = concept.get('preferredText')
            class_uri = concept.get('classUri')
            negated = concept.get('negated', False)
            uncertain = concept.get('uncertain', False)
            historic = concept.get('historic', False)
            confidence = concept.get('confidence', '')

            if dphe_group and preferred_text and class_uri:
                record = {
                    'patient_id': patient_id,
                    'dpheGroup': dphe_group,
                    'preferredText': preferred_text,
                    'classUri': class_uri,
                    'negated': negated,
                    'uncertain': uncertain,
                    'historic': historic,
                    'confidence': confidence
                }
                self.concepts_data.append(record)


    def _get_patient_file_num(self, patient_id: str) -> int:
        """Get the file number for a patient (1-indexed)."""
        if patient_id not in self.patient_set:
            return 1
        patient_idx = self.patient_order.index(patient_id)
        return (patient_idx // self.patients_per_file) + 1

    def save_to_csv(self) -> None:
        """Save any remaining extracted concept data to CSV files."""
        # Write remaining data if any
        if self.concepts_data:
            logger.info(f"Writing remaining concept data for patients {self.last_written_file_num * self.patients_per_file + 1}-{len(self.patient_order)}...")
            self._write_csv_files()
            logger.info("✓ Final concept data written")

    def _write_csv_files(self) -> None:
        """Write accumulated concept data to CSV file for current patient group."""
        if not self.concepts_data:
            return

        # Calculate which file number this batch belongs to
        file_num = (len(self.patient_order) // self.patients_per_file)

        # Create subdirectory
        concepts_dir = self.output_dir / 'extracted_concepts'
        concepts_dir.mkdir(parents=True, exist_ok=True)

        # Write concepts
        concepts_file = concepts_dir / f'extracted_concepts_{file_num}.csv'
        with open(concepts_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['patient_id', 'dpheGroup', 'preferredText', 'classUri', 'negated', 'uncertain', 'historic', 'confidence']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.concepts_data)
        logger.info(f"  Wrote {len(self.concepts_data)} concept records to extracted_concepts/{concepts_file.name}")

        # Clear accumulated data for next batch
        self.concepts_data = []
        self.last_written_file_num = file_num



def process_cancer_data(db_path: str, output_dir: Path, cancer_count: queue.Queue[int]) -> None:
    """
    Thread function to process cancer data.

    Args:
        db_path: Path to database
        output_dir: Output directory for CSV files
        cancer_count: Queue to report completion
    """
    try:
        logger.info("[CANCER THREAD] Starting cancer data extraction...")
        # Create own database connection for this thread
        db_reader = DatabaseReader(db_path)
        if not db_reader.connect():
            logger.error("[CANCER THREAD] FATAL: Failed to connect to database")
            cancer_count.put(0)
            return

        cancer_extractor = None
        cancer_file_count = 0

        for cancer_files in db_reader.get_cancer_files(limit=None):
            cancer_file_count += len(cancer_files)
            logger.info(f"[CANCER THREAD] Processing cancer chunk ({len(cancer_files)} files)...")

            if cancer_extractor is None:
                cancer_extractor = CancerDataExtractor(output_dir)

            for patient_id, cancer_data in cancer_files.items():
                try:
                    cancer_extractor.extract_from_data(cancer_data, patient_id)
                except Exception as e:
                    logger.error(f"[CANCER THREAD] ERROR: Failed to extract cancer data for patient {patient_id}: {e}")

            logger.info("[CANCER THREAD] Cancer chunk extraction complete")

        if cancer_extractor:
            logger.info("[CANCER THREAD] Saving final cancer data...")
            cancer_extractor.save_to_csv()
            logger.info(f"[CANCER THREAD] SUCCESS: Cancer data extraction and save complete ({cancer_file_count} files)")
        else:
            logger.warning("[CANCER THREAD] WARNING: No cancer files found in database")

        db_reader.disconnect()
        cancer_count.put(cancer_file_count)

    except Exception as e:
        logger.error(f"[CANCER THREAD] FATAL ERROR: {e}", exc_info=True)
        cancer_count.put(0)


def process_concept_data(db_path: str, output_dir: Path, concept_count: queue.Queue[int]) -> None:
    """
    Thread function to process concept data.

    Args:
        db_path: Path to database
        output_dir: Output directory for CSV files
        concept_count: Queue to report completion
    """
    try:
        logger.info("[CONCEPT THREAD] Starting concept data extraction...")
        # Create own database connection for this thread
        db_reader = DatabaseReader(db_path)
        if not db_reader.connect():
            logger.error("[CONCEPT THREAD] FATAL: Failed to connect to database")
            concept_count.put(0)
            return

        concept_extractor = None
        concept_file_count = 0

        # get_concept_files is now a generator that yields chunks
        for concept_files in db_reader.get_concept_files(limit=None):
            concept_file_count += len(concept_files)
            logger.info(f"[CONCEPT THREAD] Processing concept chunk ({len(concept_files)} files)...")

            if concept_extractor is None:
                concept_extractor = ConceptExtractor(output_dir)

            for patient_id, concept_data in concept_files.items():
                try:
                    concept_extractor.extract_from_data(concept_data, patient_id)
                except Exception as e:
                    logger.error(f"[CONCEPT THREAD] ERROR: Failed to extract concept data for patient {patient_id}: {e}")

            logger.info("[CONCEPT THREAD] Concept chunk extraction complete")

        if concept_extractor:
            logger.info("[CONCEPT THREAD] Saving final concept data...")
            concept_extractor.save_to_csv()
            logger.info(f"[CONCEPT THREAD] SUCCESS: Concept data extraction and save complete ({concept_file_count} files)")
        else:
            logger.warning("[CONCEPT THREAD] WARNING: No concept files found in database")

        db_reader.disconnect()
        concept_count.put(concept_file_count)

    except Exception as e:
        logger.error(f"[CONCEPT THREAD] FATAL ERROR: {e}", exc_info=True)
        concept_count.put(0)

def _count_deepphe_json_outputs(db_path: Path) -> tuple[int, int]:
    """Return counts for cancer and concept JSON outputs in the loaded files table."""
    conn = sqlite3.connect(str(db_path))
    try:
        cancer_count = conn.execute(
            "SELECT COUNT(*) FROM files WHERE filename LIKE '%_Cancers.json'"
        ).fetchone()[0]
        concept_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM files
            WHERE filename LIKE '%_Concepts.json'
              AND filename NOT LIKE 'all_concepts_%'
            """
        ).fetchone()[0]
    finally:
        conn.close()
    return int(cancer_count), int(concept_count)


def run_extraction(db_path: Path, output_dir: Path) -> tuple[int, int]:
    """Extract cancer and concept CSV shards from a DeepPhe output SQLite database."""
    db_path = db_path.resolve()
    output_dir = output_dir.resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    expected_cancers, expected_concepts = _count_deepphe_json_outputs(db_path)
    if expected_cancers == 0 or expected_concepts == 0:
        raise ValueError(
            "DeepPhe output JSON files were not found in the SQLite files table. "
            "Stage 3 requires filenames ending in *_Cancers.json and *_Concepts.json. "
            f"Found {expected_cancers} cancer file(s) and {expected_concepts} concept file(s)."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("="*80)
    logger.info("CANCER AND CONCEPT DATA EXTRACTION - PARALLEL PROCESSING")
    logger.info("="*80)
    logger.info(f"Database: {db_path}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("Processing mode: 2 parallel threads (cancer + concepts)")
    logger.info("="*80)

    cancer_count: queue.Queue[int] = queue.Queue()
    concept_count: queue.Queue[int] = queue.Queue()

    logger.info("\n" + "="*80)
    logger.info("STARTING PARALLEL PROCESSING THREADS")
    logger.info("="*80)

    cancer_thread = Thread(
        target=process_cancer_data,
        args=(str(db_path), output_dir, cancer_count),
        name="CancerThread",
        daemon=False
    )

    concept_thread = Thread(
        target=process_concept_data,
        args=(str(db_path), output_dir, concept_count),
        name="ConceptThread",
        daemon=False
    )

    logger.info("[MAIN] Starting cancer processing thread...")
    cancer_thread.start()
    logger.info("[MAIN] Starting concept processing thread...")
    concept_thread.start()

    logger.info("\n" + "="*80)
    logger.info("WAITING FOR THREADS TO COMPLETE")
    logger.info("="*80)

    cancer_thread.join()
    logger.info("[MAIN] Cancer thread completed")

    concept_thread.join()
    logger.info("[MAIN] Concept thread completed")

    cancer_file_count = cancer_count.get()
    concept_file_count = concept_count.get()

    if cancer_file_count == 0 or concept_file_count == 0:
        raise RuntimeError(
            "Extraction did not process the required DeepPhe JSON outputs. "
            f"Processed {cancer_file_count} cancer file(s) and {concept_file_count} concept file(s)."
        )

    logger.info("\n" + "="*80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Cancer files processed: {cancer_file_count}")
    logger.info(f"Concept files processed: {concept_file_count}")
    logger.info("\nOutput Files Created (organized by type):")
    logger.info(f"  {output_dir}/")
    logger.info("    extracted_tumors/")
    logger.info("      extracted_tumors_1.csv, extracted_tumors_2.csv, etc.")
    logger.info("    extracted_attributes/")
    logger.info("      extracted_attributes_1.csv, extracted_attributes_2.csv, etc.")
    logger.info("    extracted_cancers/")
    logger.info("      extracted_cancers_1.csv, extracted_cancers_2.csv, etc.")
    logger.info("    extracted_concepts/")
    logger.info("      extracted_concepts_1.csv, extracted_concepts_2.csv, etc.")
    logger.info("  (Each file contains data for up to 1000 patients)")

    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETED SUCCESSFULLY")
    logger.info("="*80)
    return cancer_file_count, concept_file_count


def main() -> int:
    """CLI entry point."""
    import argparse

    from dphe_db_pipeline.paths import DEFAULT_COMPRESSED_DB, DEFAULT_EXTRACTION_DATA_DIR

    parser = argparse.ArgumentParser(
        description="Extract cancer and concept data from a DeepPhe SQLite database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_COMPRESSED_DB,
        help=f"Path to the compressed DeepPhe SQLite database (default: {DEFAULT_COMPRESSED_DB}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXTRACTION_DATA_DIR,
        help=f"Directory for extracted CSV shards (default: {DEFAULT_EXTRACTION_DATA_DIR}).",
    )
    args = parser.parse_args()

    try:
        run_extraction(args.database, args.output_dir)
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}", exc_info=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
