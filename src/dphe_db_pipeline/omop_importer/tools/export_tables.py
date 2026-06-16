import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

_IMPORTER_DIR = Path(__file__).resolve().parents[1]


load_dotenv()

DEST_DIR = os.getenv("EXPORT_DIR", "output/exported")
os.makedirs(DEST_DIR, exist_ok=True)


def _open_sqlite(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def export_table(config, table_name, filename, column_names, delimiter):
    """Export aggregated column data from SQLite to a delimited file."""
    db_path = config['SQLITE_DB_PATH']
    with _open_sqlite(db_path) as conn:
        cursor = conn.cursor()
        output_file = os.path.join(DEST_DIR, filename)
        with open(output_file, 'w') as file:
            file.write(f"COL{delimiter}VAL{delimiter}PERSON_IDS\n")

            for column_name in column_names:
                deciles = column_name == "AGE_AT_DX"
                print(f"Processing column: {column_name}")
                query = (
                    f"SELECT `{column_name}`, PERSON_ID FROM `{table_name}` "
                    f"WHERE `{column_name}` IS NOT NULL "
                    f"ORDER BY `{column_name}`, PERSON_ID"
                )
                cursor.execute(query)

                data: dict = {}
                for row in cursor:
                    raw_val = row[0]
                    if deciles:
                        try:
                            age = int(raw_val)
                        except (TypeError, ValueError):
                            age = 0
                        if age < 20:
                            key = "0-19"
                        elif age < 30:
                            key = "20-29"
                        elif age < 40:
                            key = "30-39"
                        elif age < 50:
                            key = "40-49"
                        elif age < 60:
                            key = "50-59"
                        elif age < 70:
                            key = "60-69"
                        elif age < 80:
                            key = "70-79"
                        else:
                            key = "80+"
                    else:
                        key = raw_val
                    person_id = row[1]
                    data.setdefault(key, []).append(person_id)

                for key, person_ids in data.items():
                    file.write(f"{column_name}{delimiter}{key}{delimiter}{','.join(map(str, person_ids))}\n")

        print(f"Exported data to {output_file}")


def export_query(config, query, filename, delimiter=','):
    """
    Export the results of an SQL query from SQLite to a delimited file.

    Args:
        config (dict): Must contain 'SQLITE_DB_PATH'.
        query (str): SQL query to execute against the SQLite database.
        filename (str): Output filename (placed in DEST_DIR).
        delimiter (str): Column delimiter for the output file.
    """
    db_path = config['SQLITE_DB_PATH']
    with _open_sqlite(db_path) as conn:
        cursor = conn.cursor()
        output_file = os.path.join(DEST_DIR, filename)

        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]

            with open(output_file, 'w') as file:
                file.write(delimiter.join(columns) + '\n')

                for row in cursor:
                    values = []
                    for val in row:
                        if val is None:
                            values.append('')
                        else:
                            val_str = str(val)
                            if delimiter in val_str:
                                val_str = f'"{val_str}"'
                            values.append(val_str)
                    file.write(delimiter.join(values) + '\n')

            print(f"Exported query results to {output_file}")
            return output_file

        except Exception as e:
            print(f"Error executing query: {e}")
            return None


def run_csv_export(config):
    """Export calculated tables and SQL-defined queries to delimited files."""
    delimiter = "|"
    export_table(config, "CALCULATED_DX_DATA", "calculated_dx_data.csv", ["CANCER", "AGE_AT_DX"], delimiter)
    export_table(config, "CALCULATED_PATIENT_DATA", "calculated_patient_data.csv", ["GENDER", "RACE", "ETHNICITY"], delimiter)

    sql_dir = str(_IMPORTER_DIR / "db" / "export-queries")
    if not os.path.isdir(sql_dir):
        print(f"No export-queries directory found at {sql_dir} — skipping SQL exports.")
        return

    for sql_file in sorted(f for f in os.listdir(sql_dir) if f.endswith('.sql')):
        sql_file_path = os.path.join(sql_dir, sql_file)
        base_name = os.path.splitext(sql_file)[0]
        csv_filename = f"{base_name}.csv"

        with open(sql_file_path) as f:
            sql_query = f.read()

        export_query(config=config, query=sql_query, filename=csv_filename, delimiter=delimiter)


def load_config(required_keys=None) -> dict:
    if required_keys is None:
        required_keys = ['SQLITE_DB_PATH']

    config = {key: os.getenv(key) or '' for key in required_keys}

    missing_keys = [k for k, v in config.items() if not v]
    if missing_keys:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_keys)}. "
            "Please create a .env file or set them in your environment."
        )
    return config


def main():
    config = load_config()

    if not os.path.isdir(DEST_DIR):
        print(f"Creating export directory: {DEST_DIR}")
        os.makedirs(DEST_DIR, exist_ok=True)

    print(f"Exporting from SQLite: {config['SQLITE_DB_PATH']}")
    print(f"Export destination: {DEST_DIR}")

    run_csv_export(config)


if __name__ == "__main__":
    main()
