import sqlite3

import icd10
from icd9cms import search

from ..utils.column_ops import get_unique_matching_icd_codes
from ..utils.delete_ops import truncate_table
from ..utils.query_utils import execute_query


def _is_sqlite(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


def _placeholder(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _quote_ident(name: str) -> str:
    return f"`{str(name).replace('`', '``')}`"


def _table_ref(conn, schema: str, table: str) -> str:
    """
    MySQL uses schema.table. SQLite mode typically does not unless ATTACH DATABASE aliases exist.
    We use bare table names in SQLite mode.
    """
    if _is_sqlite(conn):
        return _quote_ident(table)
    return f"{schema}.{table}"


def _cursor_buffered_if_supported(conn):
    # mysql.connector supports buffered=True, sqlite3 does not
    if _is_sqlite(conn):
        return conn.cursor()
    return conn.cursor(buffered=True)


def _extract_after_last_colon(value):
    if value is None:
        return None
    s = str(value)
    return s.rsplit(":", 1)[-1] if ":" in s else s


def _parent3_from_condition_value(value):
    token = _extract_after_last_colon(value)
    if token is None:
        return None
    token = token.strip()
    return token[:3] if token else None


def lookup_icd_description(code, icd9=False):
    """
    Look up the description for an ICD9/ICD10 code.
    """
    if icd9:
        icd9_obj = search(code)
        if icd9_obj:
            if icd9_obj.long_desc is not None:
                return icd9_obj.long_desc
            elif icd9_obj.short_desc is not None:
                return icd9_obj.short_desc
            else:
                return icd9_obj.code
    else:
        icd10_obj = icd10.find(code)
        if icd10_obj:
            if icd10_obj.description is not None:
                return icd10_obj.description
            else:
                return icd10_obj.code
    return None


def create_icd_lookup_table(cursor, conn, icd9=False, icd10=False):
    """
    Create and populate an ICD lookup table.
    """
    table_name = ""
    if icd9:
        table_name = "icd9_lookup"
    if icd10:
        table_name = "icd10_lookup"

    truncate_table(cursor, conn, table_name)

    # SQLite-safe DDL types
    if _is_sqlite(conn):
        query = f"""
        CREATE TABLE IF NOT EXISTS {_quote_ident(table_name)} (
            code TEXT PRIMARY KEY,
            description TEXT
        );
        """
    else:
        query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            code VARCHAR(50) PRIMARY KEY,
            description TEXT
        );
        """
    execute_query(cursor=cursor, conn=conn, query=query, commit=True)

    vocab = "ICD9" if icd9 else "ICD10"

    unique_brcaova_hosp_codes = get_unique_matching_icd_codes(
        cursor,
        table_name="omop.DIAGNOSIS_BRCAOVCA_HOSP_VW",
        column_name="CONDITION_SOURCE_VALUE",
        icd_vocab=vocab,
        substring_char=":",
        index=-1,
    )
    unique_brcaova_outpt_codes = get_unique_matching_icd_codes(
        cursor,
        table_name="omop.DIAGNOSIS_BRCAOVCA_OUTPT_VW",
        column_name="CONDITION_SOURCE_VALUE",
        icd_vocab=vocab,
        substring_char=":",
        index=-1,
    )
    unique_melanoma_hosp_codes = get_unique_matching_icd_codes(
        cursor,
        table_name="omop.DIAGNOSIS_MELANOMA_HOSP_VW",
        column_name="CONDITION_SOURCE_VALUE",
        icd_vocab=vocab,
        substring_char=":",
        index=-1,
    )
    unique_melanoma_outpt_codes = get_unique_matching_icd_codes(
        cursor,
        table_name="omop.DIAGNOSIS_MELANOMA_OUTPT_VW",
        column_name="CONDITION_SOURCE_VALUE",
        icd_vocab=vocab,
        substring_char=":",
        index=-1,
    )

    unique_icd_codes = list(
        set(
            unique_brcaova_hosp_codes
            + unique_brcaova_outpt_codes
            + unique_melanoma_hosp_codes
            + unique_melanoma_outpt_codes
        )
    )

    ph = _placeholder(conn)
    insert_query = f"INSERT INTO {_quote_ident(table_name)} (code, description) VALUES ({ph}, {ph});"

    rows = []
    for code in unique_icd_codes:
        rows.append((code, lookup_icd_description(code, icd9=icd9)))

    if rows:
        cursor.executemany(insert_query, rows)
        conn.commit()


def _load_icd_code_prefix_map(cursor, conn, dest_schema, icd_codes_table="ICD_CODES"):
    """
    Build prefix -> list[(cancer, vocab_last_char)] from lookup ICD_CODES.
    """
    table_ref = _table_ref(conn, dest_schema, icd_codes_table)
    # Avoid MySQL RIGHT() for SQLite; do post-processing in Python.
    query = f"SELECT CODE, CANCER, VOCAB FROM {table_ref};"
    cursor.execute(query)

    prefix_map = {}
    for code, cancer, vocab in cursor.fetchall():
        if code is None:
            continue
        prefix = str(code)[:3]
        vocab_last = str(vocab)[-1] if vocab is not None and str(vocab) != "" else None
        prefix_map.setdefault(prefix, []).append((cancer, vocab_last))
    return prefix_map


def process_icd_operation(cursor, conn, config):
    """
    Build CALCULATED_PT_ICD_CODES from configured OMOP diagnosis source tables.

    SQLite-safe rewrite:
    - no buffered=True for sqlite
    - no MySQL LEFT/RIGHT/SUBSTRING_INDEX
    - no INSERT IGNORE in sqlite
    - no %s placeholders in sqlite
    """
    source_tables_str = config["tables"]
    source_tables = [tbl.strip() for tbl in source_tables_str.split(",") if tbl.strip()]
    source_code_column = config["code_column"]
    source_person_id_column = config["person_id_column"]
    source_date_column = config["date_column"]
    source_date_column_type = config["date_column_type"]
    source_schema = config["source_schema"]

    dest_table = config["destination_table"]
    dest_person_id_column = config["destination_person_id_column"]
    dest_date_column = config["destination_date_column"]
    dest_parent_column = config["destination_parent_column"]
    dest_icd10_cancer_column = config["destination_cancer_column"]
    dest_vocab_column = config["destination_vocab_column"]
    dest_schema = config["destination_schema"]

    truncate_table(cursor, conn, dest_table)

    # Load ICD_CODES once and match prefixes in Python (portable and simpler)
    icd_prefix_map = _load_icd_code_prefix_map(cursor, conn, dest_schema, "ICD_CODES")

    ph = _placeholder(conn)
    dest_table_ref = _table_ref(conn, dest_schema, dest_table)

    # Use INSERT OR IGNORE in SQLite, INSERT IGNORE in MySQL
    if _is_sqlite(conn):
        insert_query = f"""
        INSERT OR IGNORE INTO {dest_table_ref}
        ({_quote_ident(dest_person_id_column)}, {_quote_ident(dest_parent_column)},
         {_quote_ident(dest_date_column)}, {_quote_ident(dest_icd10_cancer_column)},
         {_quote_ident(dest_vocab_column)})
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
        """
    else:
        insert_query = f"""
        INSERT IGNORE INTO {dest_table_ref}
        ({dest_person_id_column}, {dest_parent_column}, {dest_date_column}, {dest_icd10_cancer_column}, {dest_vocab_column})
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
        """

    for table in source_tables:
        source_table = table.strip()
        print(f"Processing source table: {source_schema}.{source_table}")

        src_ref = _table_ref(conn, source_schema, source_table)

        # Portable select: raw values only, parse ICD parts in Python
        if _is_sqlite(conn):
            if source_date_column_type == "DATE":
                date_expr = f"s.{_quote_ident(source_date_column)}"
            else:
                # SQLite date(...) normalizes text-ish date values where possible
                date_expr = f"date(s.{_quote_ident(source_date_column)})"
            select_query = f"""
            SELECT
                s.{_quote_ident(source_person_id_column)} AS person_id,
                s.{_quote_ident(source_code_column)} AS condition_source_value,
                {date_expr} AS edate
            FROM {src_ref} AS s
            WHERE s.{_quote_ident(source_code_column)} LIKE '%ICD%'
            """
        else:
            date_expr = f"s.{source_date_column}"
            if source_date_column_type != "DATE":
                date_expr = f"CAST({date_expr} AS DATE)"
            select_query = f"""
            SELECT
                s.{source_person_id_column} AS person_id,
                s.{source_code_column} AS condition_source_value,
                {date_expr} AS edate
            FROM {src_ref} s
            WHERE s.{source_code_column} LIKE '%ICD%'
            """

        print(select_query)

        buffered_cursor = _cursor_buffered_if_supported(conn)
        buffered_cursor.execute(select_query)

        batch_size = 10000
        total_inserted = 0

        while True:
            batch = buffered_cursor.fetchmany(batch_size)
            if not batch:
                break

            insert_rows = []
            for person_id, condition_source_value, edate in batch:
                parent = _parent3_from_condition_value(condition_source_value)
                if not parent:
                    continue

                matches = icd_prefix_map.get(parent, [])
                if not matches:
                    continue

                for cancer, vocab_last in matches:
                    insert_rows.append((person_id, parent, edate, cancer, vocab_last))

            if insert_rows:
                cursor.executemany(insert_query, insert_rows)
                conn.commit()

                batch_count = getattr(cursor, "rowcount", 0)
                total_inserted += batch_count if batch_count is not None else 0
                print(f"Inserted batch: {len(insert_rows)} rows (Affected rows: {batch_count})")

        print(f"Total affected rows: {total_inserted}")

        try:
            buffered_cursor.close()
        except Exception:
            pass


def update_calculated_dx_data(curr, conn, icd_versions=None, cancer_types=None):
    """
    Update CALCULATED_DX_DATA table with cancer indicators from CALCULATED_PT_ICD_CODES.
    (Portable version; args kept for compatibility even if unused.)
    """
    results = {}

    try:
        cursor = curr
        insert_query = """
            INSERT INTO CALCULATED_DX_DATA (PERSON_ID, CODE, VOCAB, DATE, CANCER)
            SELECT i.PERSON_ID, i.PARENT, i.VOCAB, MIN(i.DATE), i.CANCER
            FROM CALCULATED_PT_ICD_CODES i
            GROUP BY i.PERSON_ID, i.PARENT, i.VOCAB, i.CANCER
            ORDER BY i.PERSON_ID, i.PARENT, i.VOCAB, i.CANCER
        """
        execute_query(cursor, conn, insert_query, commit=True)
        return results

    except Exception as e:
        print(f"Database error: {e}")
        return None
