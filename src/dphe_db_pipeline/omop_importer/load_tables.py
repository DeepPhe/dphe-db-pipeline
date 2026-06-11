import os

from dotenv import load_dotenv

from .run import run_csv_import

load_dotenv()


def load_config(required_keys=None) -> dict[str, str]:
    if required_keys is None:
        required_keys = ['SOURCE_DIR', 'SQLITE_DB_PATH']

    config: dict[str, str] = {key: os.getenv(key) or '' for key in required_keys}

    missing_keys = [key for key, value in config.items() if not value]
    if missing_keys:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_keys)}. "
            "Please create a .env file or set them in your environment."
        )
    return config


def main():
    config = load_config()

    source_dir: str = config['SOURCE_DIR'] or ''
    if not source_dir or not os.path.isdir(source_dir):
        print(f"Error: The directory {source_dir!r} does not exist or is not a directory.")
        return

    print(config)

    csv_files = [
        os.path.join(source_dir, f)
        for f in os.listdir(source_dir)
        if f.lower().endswith('.csv')
    ]

    print(f"Found {len(csv_files)} CSV files to process")

    run_csv_import(csv_files, config)


if __name__ == "__main__":
    main()
