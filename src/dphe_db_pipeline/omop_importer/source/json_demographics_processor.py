import json
import logging
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_UNKNOWN_VALUES = {"", "unknown", "unk", "na", "n/a", "none", "null"}
_CANCER_MAP = {
    "breastcancer": "B",
    "ovariancancer": "O",
    "melanoma": "M",
    "b": "B",
    "o": "O",
    "m": "M",
}


def _to_clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _normalize_date(value: Any) -> str | None:
    text = _to_clean_text(value)
    if text is None:
        return None

    lowered = text.lower()
    if lowered in _UNKNOWN_VALUES:
        return None

    # Prefer project-specified MM-DD-YYYY; allow ISO for convenience.
    for fmt in ("%m-%d-%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _normalize_age(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, str) and value.strip().lower() in _UNKNOWN_VALUES:
        return None

    try:
        age = int(float(value))
    except (TypeError, ValueError):
        return None

    if age < 0:
        return None
    return age


def _normalize_cancer(value: Any) -> str | None:
    text = _to_clean_text(value)
    if text is None:
        return None

    key = text.replace("_", "").replace("-", "").replace(" ", "").lower()
    return _CANCER_MAP.get(key)


def _ensure_json_mode_tables(cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS `CALCULATED_PATIENT_DATA` (
            `PERSON_ID` TEXT PRIMARY KEY,
            `GENDER` TEXT,
            `RACE` TEXT,
            `ETHNICITY` TEXT,
            `DATE_OF_BIRTH` TEXT
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS `CALCULATED_DX_DATA` (
            `PERSON_ID` TEXT PRIMARY KEY,
            `CODE` TEXT,
            `VOCAB` TEXT,
            `DATE` TEXT,
            `CANCER` TEXT,
            `AGE_AT_DX` INTEGER
        );
        """
    )
    conn.commit()


def _upsert_patient(
    cursor: sqlite3.Cursor,
    conn: sqlite3.Connection,
    person_id: str,
    gender: str | None,
    race: str | None,
    ethnicity: str | None,
    date_of_birth: str | None,
) -> tuple[bool, bool]:
    cursor.execute(
        """
        UPDATE `CALCULATED_PATIENT_DATA`
        SET `GENDER` = ?, `RACE` = ?, `ETHNICITY` = ?, `DATE_OF_BIRTH` = ?
        WHERE `PERSON_ID` = ?;
        """,
        (gender, race, ethnicity, date_of_birth, person_id),
    )
    updated = cursor.rowcount > 0

    cursor.execute(
        """
        INSERT INTO `CALCULATED_PATIENT_DATA` (`PERSON_ID`, `GENDER`, `RACE`, `ETHNICITY`, `DATE_OF_BIRTH`)
        SELECT ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM `CALCULATED_PATIENT_DATA` WHERE `PERSON_ID` = ?
        );
        """,
        (person_id, gender, race, ethnicity, date_of_birth, person_id),
    )
    inserted = cursor.rowcount > 0
    conn.commit()
    return inserted, updated


def _upsert_dx(
    cursor: sqlite3.Cursor,
    conn: sqlite3.Connection,
    person_id: str,
    cancer: str | None,
    age_at_dx: int | None,
) -> tuple[bool, bool]:
    cursor.execute(
        """
        UPDATE `CALCULATED_DX_DATA`
        SET `CANCER` = ?, `AGE_AT_DX` = ?
        WHERE `PERSON_ID` = ?;
        """,
        (cancer, age_at_dx, person_id),
    )
    updated = cursor.rowcount > 0

    cursor.execute(
        """
        INSERT INTO `CALCULATED_DX_DATA` (`PERSON_ID`, `CANCER`, `AGE_AT_DX`)
        SELECT ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM `CALCULATED_DX_DATA` WHERE `PERSON_ID` = ?
        );
        """,
        (person_id, cancer, age_at_dx, person_id),
    )
    inserted = cursor.rowcount > 0
    conn.commit()
    return inserted, updated


def _load_json_files(json_path: str) -> Iterable[dict[str, Any]]:
    if os.path.isfile(json_path):
        with open(json_path, encoding="utf-8") as handle:
            yield json.load(handle)
        return

    if os.path.isdir(json_path):
        for file_name in sorted(os.listdir(json_path)):
            if not file_name.lower().endswith(".json"):
                continue
            file_path = os.path.join(json_path, file_name)
            with open(file_path, encoding="utf-8") as handle:
                yield json.load(handle)
        return

    raise FileNotFoundError(f"JSON_SOURCE_PATH does not exist: {json_path}")


def run_json_import(json_path: str, sqlite_conn: sqlite3.Connection, sqlite_cursor: sqlite3.Cursor) -> None:
    """
    Import patient demographics JSON payload(s) into SQLite calculated tables.

    JSON schema shape expected:
    {
      "patients": [
        {
          "PatientID": "...",
          "Gender": "...",
          "Race": "...",
          "DateOfBirth": "MM-DD-YYYY",
          "CancerType": "BreastCancer|OvarianCancer|Melanoma",
          "AgeAtDiagnosis": 50
        }
      ]
    }
    """
    _ensure_json_mode_tables(sqlite_cursor, sqlite_conn)

    patient_inserts = patient_updates = 0
    dx_inserts = dx_updates = 0
    skipped = 0

    for payload in _load_json_files(json_path):
        patients = payload.get("patients", []) if isinstance(payload, dict) else []
        if not isinstance(patients, list):
            raise ValueError("JSON payload must contain a 'patients' array.")

        for record in patients:
            if not isinstance(record, dict):
                skipped += 1
                continue

            person_id = _to_clean_text(record.get("PatientID"))
            if not person_id:
                skipped += 1
                continue

            gender = _to_clean_text(record.get("Gender"))
            race = _to_clean_text(record.get("Race"))
            ethnicity = _to_clean_text(record.get("Ethnicity"))
            date_of_birth = _normalize_date(record.get("DateOfBirth"))
            cancer = _normalize_cancer(record.get("CancerType"))
            age_at_dx = _normalize_age(record.get("AgeAtDiagnosis"))

            inserted, updated = _upsert_patient(
                sqlite_cursor,
                sqlite_conn,
                person_id,
                gender,
                race,
                ethnicity,
                date_of_birth,
            )
            patient_inserts += int(inserted)
            patient_updates += int(updated)

            inserted, updated = _upsert_dx(
                sqlite_cursor,
                sqlite_conn,
                person_id,
                cancer,
                age_at_dx,
            )
            dx_inserts += int(inserted)
            dx_updates += int(updated)

    logger.info(
        "JSON import complete. "
        "CALCULATED_PATIENT_DATA inserted=%d, updated=%d; "
        "CALCULATED_DX_DATA inserted=%d, updated=%d; skipped=%d",
        patient_inserts,
        patient_updates,
        dx_inserts,
        dx_updates,
        skipped,
    )

