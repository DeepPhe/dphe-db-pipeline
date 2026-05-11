import argparse
import json
import os
import sqlite3
import multiprocessing as mp
from functools import partial
from pathlib import Path

from .db.omap.lookup_table_ops import create_lookup_tables
from .db.omap.translate_ops import process_translation
from .db.utils.delete_ops import drop_table
from dotenv import load_dotenv, dotenv_values
from .reports.age_cancer import (
    visualize_age_distribution_by_cancer,
    visualize_age_distribution_by_demographic_and_cancer,
    visualize_cancer_counts_by_demographics,
)

from .source.config_processor import (
    add_indexes_after_update,
    add_indexes_before_update,
    change_column_types,
    create_columns,
    process_csv_file,
)
from .source.json_demographics_processor import run_json_import

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# Valid source types
# ---------------------------------------------------------------------------
VALID_SOURCE_TYPES = ('csv', 'mysql', 'json')


def print_env_instructions():
    """Print instructions for creating a valid .env file."""
    instructions = (
        "Please create a .env file in your project root with the following content:\n\n"
        "# Ingestion source: csv | mysql | json\n"
        "SOURCE_TYPE=csv\n\n"
        "# Always required — destination database\n"
        "SQLITE_DB_PATH=output/databases/deepphe.sqlite3\n\n"
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
    print(instructions)


def check_env():
    """
    Validate .env file contains required fields for the selected SOURCE_TYPE.

    Always required:
      - SOURCE_TYPE  (csv | mysql | json)
      - SQLITE_DB_PATH

    SOURCE_TYPE=csv also requires:
      - SOURCE_DIR

    SOURCE_TYPE=mysql also requires:
      - MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

    SOURCE_TYPE=json also requires:
      - JSON_SOURCE_PATH

    Returns:
        bool: True if all required fields are present.
    """
    env_file = ".env"
    if not os.path.exists(env_file):
        print("Error: .env file not found.")
        print_env_instructions()
        return False

    env_values = dotenv_values(env_file)

    # Always required
    always_required = {"SOURCE_TYPE", "SQLITE_DB_PATH"}
    missing = [f for f in always_required if not env_values.get(f)]
    if missing:
        print(f"Error: Missing required fields: {', '.join(missing)}")
        print_env_instructions()
        return False

    source_type = env_values.get("SOURCE_TYPE", "").lower()
    if source_type not in VALID_SOURCE_TYPES:
        print(f"Error: Invalid SOURCE_TYPE '{source_type}'. Must be one of: {', '.join(VALID_SOURCE_TYPES)}")
        print_env_instructions()
        return False

    # CSV mode needs SOURCE_DIR
    if source_type == 'csv' and not env_values.get("SOURCE_DIR"):
        print("Error: SOURCE_DIR is required when SOURCE_TYPE is 'csv'.")
        print_env_instructions()
        return False

    # JSON mode needs a JSON source path
    if source_type == 'json' and not env_values.get("JSON_SOURCE_PATH"):
        print("Error: JSON_SOURCE_PATH is required when SOURCE_TYPE=json.")
        print_env_instructions()
        return False

    # MySQL source needs connection details
    if source_type == 'mysql':
        mysql_fields = {"MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"}
        missing_mysql = [f for f in mysql_fields if not env_values.get(f)]
        if missing_mysql:
            print(f"Error: Missing MySQL source fields: {', '.join(missing_mysql)}")
            print_env_instructions()
            return False

    print("All required fields are present in the .env file.")
    return True


def load_config() -> dict:
    """
    Load configuration from environment variables.

    The destination is always SQLite; SOURCE_TYPE controls where data is read from.

    Returns:
        dict: Configuration values.
    """
    source_type = os.getenv('SOURCE_TYPE', 'csv').lower()
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            f"Invalid SOURCE_TYPE '{source_type}'. Must be one of: {', '.join(VALID_SOURCE_TYPES)}. "
            "Please check your .env file."
        )

    config: dict = {
        'SOURCE_TYPE': source_type,
        'SQLITE_DB_PATH': os.getenv('SQLITE_DB_PATH', ''),
    }

    if not config['SQLITE_DB_PATH']:
        raise ValueError("SQLITE_DB_PATH is required in your .env file.")

    if source_type in ('csv', 'json'):
        config['SOURCE_DIR'] = os.getenv('SOURCE_DIR', '')

    if source_type == 'json':
        config['JSON_SOURCE_PATH'] = os.getenv('JSON_SOURCE_PATH', '')
        if not config['JSON_SOURCE_PATH']:
            raise ValueError("JSON_SOURCE_PATH is required when SOURCE_TYPE=json.")

    if source_type == 'mysql':
        for key in ('MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE'):
            config[key] = os.getenv(key, '')
        missing = [k for k, v in config.items() if k.startswith('MYSQL_') and not v]
        if missing:
            raise ValueError(f"Missing MySQL source variables: {', '.join(missing)}")

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
    try:
        conn = _open_sqlite(config['SQLITE_DB_PATH'])
        cursor = conn.cursor()
        process_csv_file(cursor, conn, csv_path, batch_size=batch_size)
        cursor.close()
        conn.close()
        print(f"Completed processing {os.path.basename(csv_path)}")
    except Exception as e:
        print(f"Error processing {os.path.basename(csv_path)}: {e}")


def run_csv_import(csv_files, config):
    """Import CSV files into SQLite using a multiprocessing pool."""
    with mp.Pool(processes=1) as pool:
        worker_func = partial(process_file_worker, config=config, batch_size=5000)
        pool.map(worker_func, csv_files)


def run_mysql_source_import(config, sqlite_cursor, sqlite_conn):
    """
    Read source tables from MySQL (read-only) and write them into SQLite.

    Uses SELECT on the MySQL source and INSERT into SQLite destination,
    never committing or writing anything back to MySQL.
    """
    try:
        import mysql.connector  # conditional import — only needed for mysql source
    except ImportError:
        raise RuntimeError("mysql-connector-python is required for SOURCE_TYPE=mysql. Run: uv sync")

    print("Connecting to MySQL source (read-only)...")
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
        print(f"Found {len(tables)} tables in MySQL source: {tables}")

        for table_name in tables:
            print(f"Importing MySQL source table: {table_name}")
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
                print(f"  {total} rows inserted into {table_name}")

            print(f"Done importing {table_name}: {total} total rows.")

        mysql_cursor.close()
    finally:
        mysql_conn.close()
        print("MySQL source connection closed.")


def main():
    parser = argparse.ArgumentParser(
        description="OMAP data importer — destination is always SQLite."
    )
    parser.add_argument("--config", required=True, help="Path to the pipeline configuration JSON file")
    parser.add_argument(
        "--source-type",
        choices=VALID_SOURCE_TYPES,
        default=None,
        help="Override SOURCE_TYPE from .env (csv | mysql | json)",
    )
    args = parser.parse_args()

    with open(args.config, 'r') as config_file:
        tasks_config = json.load(config_file)

    # Resolve lookup_tables_dir relative to the config file so it works from any CWD
    config_dir = Path(args.config).resolve().parent
    lookup_cfg = tasks_config.get("before_update", {}).get("add_lookup_tables", {})
    if lookup_cfg and not Path(lookup_cfg.get("lookup_tables_dir", "")).is_absolute():
        lookup_cfg["lookup_tables_dir"] = str(config_dir / lookup_cfg["lookup_tables_dir"])

    config = load_config()

    # Ensure the SQLite output directory exists
    sqlite_path = os.getenv('SQLITE_DB_PATH', '')
    if sqlite_path:
        os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)

    # CLI override takes precedence over .env
    if args.source_type:
        config['SOURCE_TYPE'] = args.source_type

    source_type = config['SOURCE_TYPE']
    print(f"SOURCE_TYPE: {source_type}")
    print(f"SQLITE_DB_PATH: {config['SQLITE_DB_PATH']}")

    # ---------------------------------------------------------------------------
    # Destination connections — always SQLite
    # ---------------------------------------------------------------------------
    omap_conn = _open_sqlite(config['SQLITE_DB_PATH'])
    omap_cursor = omap_conn.cursor()

    lookup_conn = _open_sqlite(config['SQLITE_DB_PATH'])
    lookup_cursor = lookup_conn.cursor()

    cursors = {'omap': omap_cursor, 'lookup': lookup_cursor}
    conns   = {'omap': omap_conn,   'lookup': lookup_conn}

    # ---------------------------------------------------------------------------
    # Source ingestion (what changes per mode; destination is always the same)
    # ---------------------------------------------------------------------------
    if source_type == 'csv':
        source_dir = str(config.get('SOURCE_DIR', ''))
        if not os.path.isdir(source_dir):
            print(f"Error: SOURCE_DIR '{source_dir}' does not exist or is not a directory.")
            return
        csv_files = [
            os.path.join(source_dir, f)
            for f in os.listdir(source_dir)
            if f.lower().endswith('.csv')
        ]
        print(f"Found {len(csv_files)} CSV files — importing into SQLite...")
        run_csv_import(csv_files, config)
        print("CSV import complete.")

    elif source_type == 'mysql':
        run_mysql_source_import(config, omap_cursor, omap_conn)
        print("MySQL source import complete.")

    elif source_type == 'json':
        json_path = config.get('JSON_SOURCE_PATH', '')
        print(f"JSON ingestion mode enabled — source: {json_path}")

    # ---------------------------------------------------------------------------
    # Pipeline steps — always run against SQLite destination
    # ---------------------------------------------------------------------------
    print("\nDropping calculated tables for fresh rebuild...")
    drop_table(cursors['lookup'], conns['lookup'], "calculated_dx_data", True)
    drop_table(cursors['lookup'], conns['lookup'], "calculated_pt_icd_codes", True)
    drop_table(cursors['lookup'], conns['lookup'], "calculated_patient_data", True)
    drop_table(cursors['lookup'], conns['lookup'], "snomed_codes", True)

    if source_type != 'json':
        # Source-table-dependent steps (skipped in JSON mode where source tables don't exist)
        change_column_types(cursors, conns, tasks_config)
        add_indexes_before_update(cursors, tasks_config, conns)
        create_lookup_tables(cursors, conns, tasks_config["before_update"]["add_lookup_tables"])
        create_columns(cursors, conns, tasks_config)
        add_indexes_after_update(cursors, tasks_config, conns)
        process_translation(cursors, conns, tasks_config)
    else:
        print("Skipping source-table-dependent pipeline steps in JSON mode.")
        run_json_import(config['JSON_SOURCE_PATH'], lookup_conn, lookup_cursor)

    # ---------------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------------
    for cursor in cursors.values():
        cursor.close()
    for conn in conns.values():
        conn.close()

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
