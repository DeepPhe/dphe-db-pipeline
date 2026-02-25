#!/usr/bin/env python3
"""
Split extracted CSV files into chunks of 1000 patients each.

Reads the full extracted_*.csv files and creates split files:
- extracted_tumors_1.csv, extracted_tumors_2.csv, etc.
- extracted_attributes_1.csv, extracted_attributes_2.csv, etc.
- extracted_cancers_1.csv, extracted_cancers_2.csv, etc.
- extracted_concepts_1.csv, extracted_concepts_2.csv, etc.

Each file contains data for a specific range of patients (1000 patients per file).
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Set

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)-8s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CSVSplitter:
    """Split CSV files by patient groups."""

    def __init__(self, input_dir: Path, output_dir: Path, patients_per_file: int = 1000):
        """
        Initialize the splitter.

        Args:
            input_dir: Directory containing the full CSV files
            output_dir: Directory for output split files
            patients_per_file: Number of patients per output file (default 1000)
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.patients_per_file = patients_per_file
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_unique_patients(self, csv_file: Path) -> List[str]:
        """
        Get unique patients from a CSV file in order of appearance.

        Args:
            csv_file: Path to CSV file

        Returns:
            List of unique patient IDs in order
        """
        patients = []
        seen = set()

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                patient_id = row.get('patient_id', '')
                if patient_id and patient_id not in seen:
                    patients.append(patient_id)
                    seen.add(patient_id)

        return patients

    def _create_patient_to_file_mapping(self, all_patients: List[str]) -> Dict[str, int]:
        """
        Map each patient to their file number (1-indexed).

        Args:
            all_patients: List of all unique patients

        Returns:
            Dictionary mapping patient_id to file number
        """
        mapping = {}
        for idx, patient_id in enumerate(all_patients):
            file_num = (idx // self.patients_per_file) + 1
            mapping[patient_id] = file_num

        return mapping

    def split_csv_file(self, csv_file: Path, patient_mapping: Dict[str, int]) -> None:
        """
        Split a single CSV file based on patient mapping.

        Args:
            csv_file: Path to input CSV file
            patient_mapping: Mapping of patient_id to file number
        """
        base_name = csv_file.stem  # Remove .csv extension
        file_writers = {}  # file_num -> (file_handle, csv_writer)
        file_handles = {}  # file_num -> file_handle

        logger.info(f"\nProcessing {csv_file.name}...")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

                if not fieldnames:
                    logger.error(f"No fieldnames found in {csv_file.name}")
                    return

                row_count = 0
                file_counts = {}  # Track row counts per file

                for row in reader:
                    patient_id = row.get('patient_id', '')

                    if not patient_id or patient_id not in patient_mapping:
                        logger.warning(f"Skipped row with unknown patient_id: {patient_id}")
                        continue

                    file_num = patient_mapping[patient_id]

                    # Create output file if needed
                    if file_num not in file_writers:
                        output_file = self.output_dir / f"{base_name}_{file_num}.csv"
                        f_handle = open(output_file, 'w', newline='', encoding='utf-8')
                        writer = csv.DictWriter(f_handle, fieldnames=fieldnames)
                        writer.writeheader()
                        file_writers[file_num] = (f_handle, writer)
                        file_handles[file_num] = f_handle
                        file_counts[file_num] = 0

                    # Write row to appropriate file
                    _, writer = file_writers[file_num]
                    writer.writerow(row)
                    file_counts[file_num] += 1
                    row_count += 1

                # Close all open files
                for f_handle in file_handles.values():
                    f_handle.close()

                logger.info(f"✓ {csv_file.name}: Split into {len(file_counts)} files")
                for file_num in sorted(file_counts.keys()):
                    logger.info(f"  - {base_name}_{file_num}.csv: {file_counts[file_num]} rows")
                logger.info(f"  Total rows processed: {row_count}")

        except Exception as e:
            logger.error(f"Error processing {csv_file.name}: {e}")
            # Close any open files
            for f_handle in file_handles.values():
                try:
                    f_handle.close()
                except:
                    pass

    def split_all_files(self) -> None:
        """Split all CSV files in the input directory."""
        logger.info("="*80)
        logger.info("CSV FILE SPLITTER - Split by Patient Groups")
        logger.info("="*80)
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Patients per file: {self.patients_per_file}")
        logger.info("="*80)

        # Find all CSV files
        csv_files = sorted(self.input_dir.glob("extracted_*.csv"))

        if not csv_files:
            logger.error("No CSV files found in input directory")
            return

        logger.info(f"\nFound {len(csv_files)} CSV files to process")

        # Get unique patients from first file to determine mapping
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Scanning for unique patients...")
        logger.info("="*80)

        # Use concepts file as reference (has most patients)
        reference_file = None
        for f in csv_files:
            if 'concepts' in f.name:
                reference_file = f
                break

        if not reference_file:
            reference_file = csv_files[0]

        logger.info(f"Using {reference_file.name} to determine patient groups...")
        all_patients = self._get_unique_patients(reference_file)
        logger.info(f"✓ Found {len(all_patients)} unique patients")

        # Calculate file groupings
        num_output_files = (len(all_patients) + self.patients_per_file - 1) // self.patients_per_file
        logger.info(f"✓ Will create {num_output_files} output files")
        logger.info(f"  - Files 1-{num_output_files-1}: {self.patients_per_file} patients each")
        logger.info(f"  - File {num_output_files}: {len(all_patients) % self.patients_per_file or self.patients_per_file} patients")

        # Create patient to file mapping
        patient_mapping = self._create_patient_to_file_mapping(all_patients)

        # Split each CSV file
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Splitting CSV files...")
        logger.info("="*80)

        for csv_file in csv_files:
            self.split_csv_file(csv_file, patient_mapping)

        # Summary
        logger.info("\n" + "="*80)
        logger.info("SPLITTING COMPLETE")
        logger.info("="*80)
        logger.info(f"✓ Successfully split {len(csv_files)} CSV files")
        logger.info(f"✓ Output files created in: {self.output_dir}")
        logger.info(f"✓ Each file contains data for up to {self.patients_per_file} patients")
        logger.info(f"✓ Total of {num_output_files} output files per CSV type")
        logger.info("\nOutput files created:")
        for csv_file in csv_files:
            base_name = csv_file.stem
            for i in range(1, num_output_files + 1):
                output_file = self.output_dir / f"{base_name}_{i}.csv"
                if output_file.exists():
                    size = output_file.stat().st_size
                    logger.info(f"  - {output_file.name} ({size:,} bytes)")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent.parent
    input_dir = base_dir / 'extracted_cancer_data'
    output_dir = base_dir / 'extracted_cancer_data_split'

    logger.info("Starting CSV splitter...")

    splitter = CSVSplitter(input_dir, output_dir, patients_per_file=1000)
    splitter.split_all_files()

    logger.info("\n✓ CSV splitting completed successfully!")


if __name__ == "__main__":
    main()
