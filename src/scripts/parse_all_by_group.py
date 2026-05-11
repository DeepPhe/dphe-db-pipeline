#!/usr/bin/env python3
"""
Master script to run all parse_*_by_group.py scripts in parallel threads.

Executes:
- parse_concepts_by_group.py
- parse_attributes_by_group.py
- parse_cancers_by_group.py
- parse_tumors_by_group.py

Each script runs in its own thread for concurrent execution.
"""

import logging
from pathlib import Path
from threading import Thread
from typing import List
import sys
import importlib.util

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)-18s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_and_run_script(script_name: str, script_path: Path) -> None:
    """
    Load and execute a script module in the current thread.

    Args:
        script_name: Name of the script (for logging)
        script_path: Path to the script file
    """
    try:
        logger.info(f"Starting execution of {script_name}...")

        # Load the module from the script file
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        if spec is None or spec.loader is None:
            logger.error(f"Failed to load {script_name}: Could not create module spec")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[script_name] = module
        spec.loader.exec_module(module)

        # Call the main function if it exists
        if hasattr(module, 'main'):
            module.main()
            logger.info(f"Completed {script_name}")
        else:
            logger.warning(f"No main() function found in {script_name}")

    except Exception as e:
        logger.error(f"Error running {script_name}: {str(e)}", exc_info=True)


def main():
    """Main entry point - execute all parse scripts in parallel threads."""
    parsers_dir = Path(__file__).parent / "parsers"

    # Define scripts to run
    scripts = [
        ("parse_concepts_by_group", parsers_dir / "parse_concepts_by_group.py"),
        ("parse_attributes_by_group", parsers_dir / "parse_attributes_by_group.py"),
        ("parse_cancers_by_group", parsers_dir / "parse_cancers_by_group.py"),
        ("parse_tumors_by_group", parsers_dir / "parse_tumors_by_group.py"),
    ]

    # Verify all scripts exist
    missing_scripts = []
    for script_name, script_path in scripts:
        if not script_path.exists():
            missing_scripts.append(str(script_path))

    if missing_scripts:
        logger.error("The following required scripts are missing:")
        for path in missing_scripts:
            logger.error(f"  - {path}")
        return

    logger.info("="*80)
    logger.info("STARTING PARALLEL EXECUTION OF ALL PARSE SCRIPTS")
    logger.info("="*80)
    logger.info(f"Parsers directory: {parsers_dir}")
    logger.info(f"Scripts to execute: {len(scripts)}")
    for script_name, _ in scripts:
        logger.info(f"  - {script_name}")
    logger.info("="*80 + "\n")

    # Create threads for each script
    threads: List[Thread] = []
    for script_name, script_path in scripts:
        thread = Thread(
            target=load_and_run_script,
            args=(script_name, script_path),
            name=script_name,
            daemon=False
        )
        threads.append(thread)

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    logger.info("\n" + "="*80)
    logger.info("ALL PARSE SCRIPTS COMPLETED")
    logger.info("="*80)
    logger.info("\nGenerated output files:")
    logger.info("  - extracted_cancer_data/concepts_by_group.csv")
    logger.info("  - extracted_cancer_data/attributes_by_group.csv")
    logger.info("  - extracted_cancer_data/cancers_by_group.csv")
    logger.info("  - extracted_cancer_data/tumors_by_group.csv")
    logger.info("="*80)


if __name__ == "__main__":
    main()
