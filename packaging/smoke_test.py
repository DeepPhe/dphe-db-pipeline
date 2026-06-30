"""Smoke-test a frozen dphe-pipeline executable without relying on Python at runtime."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile


def _run(binary: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()

    help_result = _run(binary, "--help")
    if help_result.returncode != 0 or "DEEPPHE" not in help_result.stdout.upper():
        raise RuntimeError(
            f"Frozen --help failed ({help_result.returncode}).\n"
            f"stdout:\n{help_result.stdout}\nstderr:\n{help_result.stderr}"
        )

    with tempfile.TemporaryDirectory(prefix="dphe-pipeline-smoke-") as temp_dir:
        work_dir = Path(temp_dir)
        run_result = _run(binary, cwd=work_dir)
        expected = work_dir / "output" / "databases" / "individual" / "deepphe.sqlite3"
        summaries = work_dir / "output" / "extraction" / "data" / "patient_summaries.jsonl"

        if run_result.returncode != 0 or not expected.is_file() or not summaries.is_file():
            raise RuntimeError(
                f"Frozen default run failed ({run_result.returncode}).\n"
                f"stdout:\n{run_result.stdout}\nstderr:\n{run_result.stderr}"
            )

    # Exercise frozen multiprocessing explicitly. The default example uses a directory,
    # while --input-zipdir dispatches zip files through worker processes.
    with tempfile.TemporaryDirectory(prefix="dphe-pipeline-multiprocess-") as temp_dir:
        work_dir = Path(temp_dir)
        zip_dir = work_dir / "zips"
        zip_dir.mkdir()
        for index in range(2):
            with ZipFile(zip_dir / f"patient-{index}.zip", "w") as archive:
                archive.writestr(f"patient-{index}.json", f'{{"patient": {index}}}')

        database = work_dir / "zipdir.sqlite3"
        multiprocessing_result = _run(
            binary,
            "--skip-importer",
            "--skip-extractor",
            "--input-zipdir",
            str(zip_dir),
            "--compressed-db",
            str(database),
            cwd=work_dir,
        )
        if multiprocessing_result.returncode != 0 or not database.is_file():
            raise RuntimeError(
                f"Frozen multiprocessing run failed ({multiprocessing_result.returncode}).\n"
                f"stdout:\n{multiprocessing_result.stdout}\n"
                f"stderr:\n{multiprocessing_result.stderr}"
            )

    print(f"Smoke test passed: {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
