import argparse
import json
import logging
import multiprocessing as mp
import os
import re
import sqlite3
from collections.abc import Mapping
from functools import partial
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from .db.omop.lookup_table_ops import create_lookup_tables
from .db.omop.translate_ops import process_translation
from .db.utils.delete_ops import drop_table
from .source.config_processor import (
    add_indexes_after_update,
    add_indexes_before_update,
    change_column_types,
    create_columns,
    process_csv_file,
)
from .source.json_demographics_processor import run_json_import

# Load environment variables from .env file (used as a fallback when explicit
# overrides are not threaded in by the caller).
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid source types
# ---------------------------------------------------------------------------
VALID_SOURCE_TYPES = ('csv', 'mysql', 'json')


def load_tasks_config(config_path: str | Path) -> dict:
    """Load importer task config from a JSON file or JS module exporting a JSON object."""
    config_path = Path(config_path)
    text = config_path.read_text(encoding="utf-8")

    if config_path.suffix == ".json":
        return json.loads(text)

    if config_path.suffix == ".js":
        body = text.strip()
        match = re.match(r"^(?:module\.exports\s*=|export\s+default)\s*", body)
        if not match:
            raise ValueError(
                f"Unsupported JS config format in {config_path}. Expected 'export default {{...}}' "
                "or 'module.exports = {...}'."
            )
        body = body[match.end():].strip()
        if body.endswith(";"):
            body = body[:-1].strip()
        return json.loads(body)

    raise ValueError(f"Unsupported config format for {config_path}. Use .json or .js.")


def print_env_instructions():
    """Log instructions for creating a valid .env file."""
    instructions = (
        "Please create a .env file in your project root with the following content:\n\n"
        "# Ingestion source: csv | mysql | json\n"
        "SOURCE_TYPE=csv\n\n"
        "# Always required — destination database\n"
        "SQLITE_DB_PATH=output/databases/individual/omop.sqlite3\n\n"
        "# Required for SOURCE_TYPE=csv (or pass it at runtime)\n"
        "SOURCE_DIR=<your_source_directory>\n\n"
        "# Required for SOURCE_TYPE=json\n"
        "JSON_SOURCE_PATH=<path_to_json_file_or_folder>\n\n"
        "# Required for SOURCE_TYPE=mysql (read-only source)\n"
        "MYSQL_HOST=<your_mysql_host>\n"
        "MYSQL_PORT=<your_mysql_port>\n"
        "MYSQL_USER=<your_mysql_user>\n"
        "MYSQL_PASSWORD=<your_mysql_password>\n"
        "MYSQL_DATABASE=<your_mysql_database>\n\n"
        "Replace the placeholders with your actual configuration."
    )
    logger.info(instructions)


_MYSQL_FIELDS = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")


def _validate_config_values(values: Mapping[str, str | None]) -> list[str]:
    """
    Validate a flat mapping of importer config values against the per-source rules.

    Single source of truth shared by ``load_config`` (which raises) and ``check_env``
    (which returns a bool). Returns a list of human-readable problems; empty == valid.

    Always required:
      - SOURCE_TYPE  (csv | mysql | json)
      - SQLITE_DB_PATH

    SOURCE_TYPE=csv also requires SOURCE_DIR; json requires JSON_SOURCE_PATH;
    mysql requires all MYSQL_* connection fields.
    """
    problems: list[str] = []

    source_type = (values.get("SOURCE_TYPE") or "").lower()
    if not source_type:
        problems.append("SOURCE_TYPE is required (csv | mysql | json).")
    elif source_type not in VALID_SOURCE_TYPES:
        problems.append(
            f"Invalid SOURCE_TYPE '{source_type}'. Must be one of: {', '.join(VALID_SOURCE_TYPES)}."
        )

    if not values.get("SQLITE_DB_PATH"):
        problems.append("SQLITE_DB_PATH is required.")

    if source_type == "csv" and not values.get("SOURCE_DIR"):
        problems.append("SOURCE_DIR is required when SOURCE_TYPE=csv.")

    if source_type == "json" and not values.get("JSON_SOURCE_PATH"):
        problems.append("JSON_SOURCE_PATH is required when SOURCE_TYPE=json.")

    if source_type == "mysql":
        missing = [key for key in _MYSQL_FIELDS if not values.get(key)]
        if missing:
            problems.append(f"Missing MySQL source fields: {', '.join(missing)}.")

    return problems


def check_env() -> bool:
    """
    Validate that a .env file in the CWD satisfies the rules for its SOURCE_TYPE.

    Delegates to the shared validator so it can never drift from ``load_config``.

    Returns:
        bool: True if all required fields are present.
    """
    env_file = ".env"
    if not os.path.exists(env_file):
        logger.error(".env file not found.")
        print_env_instructions()
        return False

    problems = _validate_config_values(dotenv_values(env_file))
    if problems:
        for problem in problems:
            logger.error("%s", problem)
        print_env_instructions()
        return False

    logger.info("All required fields are present in the .env file.")
    return True


def load_config(
    *,
    source_type: str | None = None,
    sqlite_db_path: str | Path | None = None,
    source_dir: str | Path | None = None,
    json_source_path: str | Path | None = None,
) -> dict:
    """
    Build the importer configuration from explicit overrides, falling back to env vars.

    The destination is always SQLite; SOURCE_TYPE controls where data is read from.
    Any argument left as None is resolved from the environment (.env / os.environ),
    so the standalone CLI keeps working while the pipeline threads config in directly.
    Validation uses the same rules as ``check_env`` via ``_validate_config_values``.

    Returns:
        dict: Configuration values.
    """
    source_type = (source_type or os.getenv('SOURCE_TYPE') or 'csv').lower()
    values: dict[str, str | None] = {
        'SOURCE_TYPE': source_type,
        'SQLITE_DB_PATH': str(sqlite_db_path) if sqlite_db_path else os.getenv('SQLITE_DB_PATH', ''),
        'SOURCE_DIR': str(source_dir) if source_dir else os.getenv('SOURCE_DIR', ''),
        'JSON_SOURCE_PATH': str(json_source_path) if json_source_path else os.getenv('JSON_SOURCE_PATH', ''),
        **{key: os.getenv(key, '') for key in _MYSQL_FIELDS},
    }

    problems = _validate_config_values(values)
    if problems:
        raise ValueError(" ".join(problems) + " Please check your configuration.")

    config: dict = {
        'SOURCE_TYPE': source_type,
        'SQLITE_DB_PATH': values['SQLITE_DB_PATH'],
    }
    if source_type in ('csv', 'json'):
        config['SOURCE_DIR'] = values['SOURCE_DIR']
    if source_type == 'json':
        config['JSON_SOURCE_PATH'] = values['JSON_SOURCE_PATH']
    if source_type == 'mysql':
        for key in _MYSQL_FIELDS:
            config[key] = values[key]

    return config


def _open_sqlite(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with recommended pragmas."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def process_file_worker(csv_path, config, batch_size=50000):
    """Worker function for multiprocessing CSV import — always writes to SQLite."""
    # Workers may run in spawned processes that do not inherit the parent's
    # logging handlers; configure a handler here if none exists (idempotent).
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    conn = None
    cursor = None
    try:
        conn = _open_sqlite(config['SQLITE_DB_PATH'])
        cursor = conn.cursor()
        process_csv_file(cursor, conn, csv_path, batch_size=batch_size)
        logger.info("Completed processing %s", os.path.basename(csv_path))
        return csv_path, True, ""
    except Exception as e:
        message = f"Error processing {os.path.basename(csv_path)}: {e}"
        logger.error(message)
        return csv_path, False, message
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def run_csv_import(csv_files, config):
    """Import CSV files into SQLite using a multiprocessing pool."""
    with mp.Pool(processes=2) as pool:
        worker_func = partial(process_file_worker, config=config, batch_size=5000)
        results = pool.map(worker_func, csv_files)

    failures = [message for _path, success, message in results if not success]
    if failures:
        raise RuntimeError(
            "CSV import failed for "
            f"{len(failures)} file(s): " + "; ".join(failures)
        )


def run_mysql_source_import(config, sqlite_cursor, sqlite_conn):
    """
    Read source tables from MySQL (read-only) and write them into SQLite.

    Uses SELECT on the MySQL source and INSERT into SQLite destination,
    never committing or writing anything back to MySQL.
    """
    try:
        import mysql.connector  # conditional import — only needed for mysql source
    except ImportError as exc:
        raise RuntimeError(
            "mysql-connector-python is required for SOURCE_TYPE=mysql. Run: uv sync"
        ) from exc

    logger.info("Connecting to MySQL source (read-only)...")
    mysql_conn = mysql.connector.connect(
        host=config['MYSQL_HOST'],
        port=int(config['MYSQL_PORT']),
        user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'],
        database=config['MYSQL_DATABASE'],
    )

    try:
        mysql_cursor = mysql_conn.cursor(buffered=True)
        # List all tables in the source MySQL database
        mysql_cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in mysql_cursor.fetchall()]
        logger.info("Found %d tables in MySQL source: %s", len(tables), tables)

        for table_name in tables:
            logger.info("Importing MySQL source table: %s", table_name)
            mysql_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 0;")
            columns = [desc[0] for desc in mysql_cursor.description]

            # Create destination table in SQLite
            col_defs = ", ".join(f"`{c}` TEXT" for c in columns)
            sqlite_cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`;")
            sqlite_cursor.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({col_defs});")
            sqlite_conn.commit()

            # Stream rows in batches
            mysql_cursor.execute(f"SELECT * FROM `{table_name}`;")
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(f"`{c}`" for c in columns)
            insert_sql = f"INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})"
            batch_size = 5000
            batch = []
            total = 0
            while True:
                rows = mysql_cursor.fetchmany(batch_size)
                if not rows:
                    break
                batch = [tuple(str(v) if v is not None else None for v in row) for row in rows]
                sqlite_cursor.executemany(insert_sql, batch)
                sqlite_conn.commit()
                total += len(batch)
                logger.info("  %d rows inserted into %s", total, table_name)

            logger.info("Done importing %s: %d total rows.", table_name, total)

        mysql_cursor.close()
    finally:
        mysql_conn.close()
        logger.info("MySQL source connection closed.")


def run_omop_import(
    config_path: str | Path,
    *,
    source_type: str | None = None,
    sqlite_db_path: str | Path | None = None,
    source_dir: str | Path | None = None,
    json_source_path: str | Path | None = None,
) -> None:
    """Run the OMOP importer with optional runtime overrides threaded in directly."""
    _run_omop_import(
        Path(config_path),
        source_type=source_type,
        sqlite_db_path=sqlite_db_path,
        source_dir=source_dir,
        json_source_path=json_source_path,
    )


def _run_omop_import(
    config_path: Path,
    *,
    source_type: str | None = None,
    sqlite_db_path: str | Path | None = None,
    source_dir: str | Path | None = None,
    json_source_path: str | Path | None = None,
) -> None:
    tasks_config = load_tasks_config(config_path)

    # Resolve lookup_tables_dir relative to the config file so it works from any CWD
    config_dir = config_path.resolve().parent
    lookup_cfg = tasks_config.get("before_update", {}).get("add_lookup_tables", {})
    if lookup_cfg and not Path(lookup_cfg.get("lookup_tables_dir", "")).is_absolute():
        lookup_cfg["lookup_tables_dir"] = str(config_dir / lookup_cfg["lookup_tables_dir"])

    config = load_config(
        source_type=source_type,
        sqlite_db_path=sqlite_db_path,
        source_dir=source_dir,
        json_source_path=json_source_path,
    )

    # Ensure the SQLite output directory exists
    sqlite_path = config['SQLITE_DB_PATH']
    if sqlite_path:
        os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)

    source_type = config['SOURCE_TYPE']
    logger.info("SOURCE_TYPE: %s", source_type)
    logger.info("SQLITE_DB_PATH: %s", config['SQLITE_DB_PATH'])

    # ---------------------------------------------------------------------------
    # Destination connections — always SQLite
    # ---------------------------------------------------------------------------
    omop_conn = _open_sqlite(config['SQLITE_DB_PATH'])
    omop_cursor = omop_conn.cursor()

    lookup_conn = _open_sqlite(config['SQLITE_DB_PATH'])
    lookup_cursor = lookup_conn.cursor()

    cursors = {'omop': omop_cursor, 'lookup': lookup_cursor}
    conns   = {'omop': omop_conn,   'lookup': lookup_conn}

    # ---------------------------------------------------------------------------
    # Source ingestion (what changes per mode; destination is always the same)
    # ---------------------------------------------------------------------------
    if source_type == 'csv':
        source_dir = str(config.get('SOURCE_DIR', ''))
        if not os.path.isdir(source_dir):
            raise FileNotFoundError(
                f"SOURCE_DIR '{source_dir}' does not exist or is not a directory."
            )
        csv_files = [
            os.path.join(source_dir, f)
            for f in os.listdir(source_dir)
            if f.lower().endswith('.csv')
        ]
        logger.info("Found %d CSV files — importing into SQLite...", len(csv_files))
        run_csv_import(csv_files, config)
        logger.info("CSV import complete.")

    elif source_type == 'mysql':
        run_mysql_source_import(config, omop_cursor, omop_conn)
        logger.info("MySQL source import complete.")

    elif source_type == 'json':
        json_path = config.get('JSON_SOURCE_PATH', '')
        logger.info("JSON ingestion mode enabled — source: %s", json_path)

    # ---------------------------------------------------------------------------
    # Pipeline steps — always run against SQLite destination
    # ---------------------------------------------------------------------------
    logger.info("Dropping calculated tables for fresh rebuild...")
    drop_table(cursors['lookup'], conns['lookup'], "calculated_dx_data", True)
    drop_table(cursors['lookup'], conns['lookup'], "calculated_pt_icd_codes", True)
    drop_table(cursors['lookup'], conns['lookup'], "calculated_patient_data", True)

    if source_type != 'json':
        # Source-table-dependent steps (skipped in JSON mode where source tables don't exist)
        change_column_types(cursors, conns, tasks_config)
        add_indexes_before_update(cursors, tasks_config, conns)
        create_lookup_tables(cursors, conns, tasks_config["before_update"]["add_lookup_tables"])
        create_columns(cursors, conns, tasks_config)
        add_indexes_after_update(cursors, tasks_config, conns)
        process_translation(cursors, conns, tasks_config)
    else:
        logger.info("Skipping source-table-dependent pipeline steps in JSON mode.")
        run_json_import(config['JSON_SOURCE_PATH'], lookup_conn, lookup_cursor)

    # ---------------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------------
    for cursor in cursors.values():
        cursor.close()
    for conn in conns.values():
        conn.close()

    logger.info("Pipeline complete.")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)-8s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="OMOP data importer - destination is always SQLite."
    )
    parser.add_argument(
        "--omop-config",
        dest="omop_config",
        required=True,
        help="Path to the OMOP importer configuration file (.json or .js)",
    )
    parser.add_argument(
        "--source-type",
        choices=VALID_SOURCE_TYPES,
        default=None,
        help="Override SOURCE_TYPE from .env (csv | mysql | json)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Override SOURCE_DIR for SOURCE_TYPE=csv.",
    )
    args = parser.parse_args()

    if args.source_dir and args.source_type is None:
        args.source_type = "csv"
    if args.source_dir and args.source_type != "csv":
        parser.error("--source-dir can only be used with --source-type csv.")

    try:
        run_omop_import(
            args.omop_config,
            source_type=args.source_type,
            source_dir=args.source_dir.resolve() if args.source_dir else None,
        )
    except Exception as exc:
        logger.error("Error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
