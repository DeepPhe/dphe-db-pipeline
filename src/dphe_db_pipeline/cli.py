from .extractor.create_concepts_table import main as create_concepts_table_main
from .extractor.extractors.extract_cancers import main as extract_cancers_main
from .extractor.extractors.extract_concepts import main as extract_concepts_main
from .loader.query_sqlite import main as explore_db_main


def extract_cancers_cli() -> None:
    extract_cancers_main()


def extract_concepts_cli() -> None:
    extract_concepts_main()


def explore_db_cli() -> None:
    explore_db_main()


def create_concepts_table_cli() -> None:
    create_concepts_table_main()
