import time


def execute_query(cursor, conn, query, params=None, commit=False):
    """
    Execute a single query, printing timing + affected rows.

    Returns:
        int: cursor.rowcount (driver-dependent; DDL may return -1)
    """
    print(f"Executing query:\n--{query}")
    if params is not None:
        print(f"--Params: {params}")

    start_time = time.time()
    try:
        if params is None:
            cursor.execute(query)
        else:
            cursor.execute(query, params)

        duration = time.time() - start_time
        response = f"--Affected rows: {getattr(cursor, 'rowcount', -1)}"
        print(f"--Query executed in {duration:.2f} seconds.\n--Response: {response}")

        if commit and conn:
            conn.commit()
        return getattr(cursor, "rowcount", -1)

    except Exception as e:
        duration = time.time() - start_time
        print(f"--Query failed after {duration:.2f} seconds. Error: {e}")
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        raise


def _is_retryable_db_error(exc: Exception) -> bool:
    """
    Retry only transient-ish failures. Do NOT retry syntax errors.
    """
    msg = str(exc).lower()

    retry_markers = [
        "database is locked",
        "lock wait timeout",
        "deadlock",
        "temporarily unavailable",
        "timeout",
        "try restarting transaction",
    ]
    non_retry_markers = [
        "syntax error",
        "near \"%\"",
        "no such table",
        "no such column",
        "unknown column",
        "has no column named",
    ]

    if any(marker in msg for marker in non_retry_markers):
        return False
    return any(marker in msg for marker in retry_markers)


def execute_many_query(
    cursor,
    conn,
    query,
    data,
    commit=False,
    max_attempts=10,
    retry_delay_seconds=5,
):
    """
    Execute a batch query using executemany, with selective retries.
    """
    if data is None:
        raise ValueError("execute_many_query received data=None")

    if not isinstance(data, (list, tuple)):
        data = list(data)

    if len(data) == 0:
        print("Batch query skipped: no rows.")
        return 0

    attempt = 1
    last_exc = None

    while attempt <= max_attempts:
        start_time = time.time()
        try:
            cursor.executemany(query, data)
            duration = time.time() - start_time
            response = f"Affected rows: {getattr(cursor, 'rowcount', -1)}"
            print(f"Batch query executed in {duration:.2f} seconds. {response}")

            if commit and conn:
                conn.commit()
            return getattr(cursor, "rowcount", -1)

        except Exception as e:
            last_exc = e
            duration = time.time() - start_time
            print(f"Attempt {attempt}/{max_attempts}: Batch query failed after {duration:.2f} seconds. Error: {e}")

            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass

            # Don't waste time retrying syntax/missing-table/etc.
            if not _is_retryable_db_error(e):
                raise

            if attempt < max_attempts:
                print(f"Waiting {retry_delay_seconds} seconds before retry...")
                time.sleep(retry_delay_seconds)

            attempt += 1

    print(f"Batch query failed after {max_attempts} attempts.")
    raise last_exc