"""Shared filesystem conventions for the DeepPhe pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path.cwd() / "output"

DEFAULT_INPUT_DIR = PACKAGE_ROOT / "resources" / "example" / "dphe_output"
DEFAULT_OMOP_DEMOGRAPHICS = (
    PACKAGE_ROOT / "resources" / "example" / "omop_data" / "patient_demographics.json"
)
DEFAULT_COMPRESSED_DB = DEFAULT_OUTPUT_ROOT / "databases" / "individual" / "deepphe.sqlite3"
DEFAULT_OMOP_DB = DEFAULT_OUTPUT_ROOT / "databases" / "individual" / "omop.sqlite3"
DEFAULT_IMPORTER_CONFIG = PACKAGE_ROOT / "omop_importer" / "omop-config.js"
DEFAULT_EXTRACTION_DATA_DIR = DEFAULT_OUTPUT_ROOT / "extraction" / "data"


@dataclass(frozen=True)
class PipelinePaths:
    """Resolved paths used by a full pipeline run."""

    input_dir: Path | None = DEFAULT_INPUT_DIR
    input_zip: Path | None = None
    input_zipdir: Path | None = None
    demographics: Path | None = DEFAULT_OMOP_DEMOGRAPHICS
    compressed_db: Path = DEFAULT_COMPRESSED_DB
    omop_db: Path = DEFAULT_OMOP_DB
    importer_config: Path = DEFAULT_IMPORTER_CONFIG
    extraction_data_dir: Path = DEFAULT_EXTRACTION_DATA_DIR
