"""Task 7.2.1 — DuckDB check runner for company data quality checks."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import duckdb


@dataclass
class CheckResult:
    violation_count: int
    affected_count: int
    sample_rows: list[dict]       # up to 20 rows
    elapsed_seconds: float
    error: str | None = None      # set if the query failed


# Tokens that are not allowed anywhere in the SQL body (case-insensitive, whole-word).
_BANNED_TOKENS = {
    "COPY", "ATTACH", "INSTALL", "PRAGMA", "CREATE", "DROP",
    "INSERT", "UPDATE", "DELETE", "EXEC", "EXECUTE", "IMPORT",
}


def _validate_sql(sql: str) -> str:
    """Validate and normalise *sql*.

    Returns the cleaned SQL string (trailing semicolon stripped).
    Raises ``ValueError`` with a descriptive reason on any violation.
    """
    # Strip leading/trailing whitespace and semicolons.
    cleaned = sql.strip().rstrip(";").strip()

    if not cleaned:
        raise ValueError("Unsafe SQL: empty statement")

    # First non-whitespace word must be SELECT or WITH.
    first_word = cleaned.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        raise ValueError(
            f"Unsafe SQL: statement must start with SELECT or WITH, got {first_word!r}"
        )

    # Reject banned tokens (whole-word, case-insensitive).
    upper_body = cleaned.upper()
    for token in _BANNED_TOKENS:
        # \b word-boundary match.
        if re.search(rf"\b{token}\b", upper_body):
            raise ValueError(f"Unsafe SQL: forbidden token {token!r}")

    # Reject multiple statements (semicolon in the body).
    if ";" in cleaned:
        raise ValueError("Unsafe SQL: multiple statements detected (semicolon in body)")

    return cleaned


def _substitute_params(sql: str, params: dict[str, tuple]) -> str:
    """Replace ``{placeholder}`` markers in *sql* with their safe SQL literals.

    ``params`` maps placeholder name → ``(value, kind)`` for number/string/bool,
    or ``(value, "duration", unit)`` for duration.
    """
    for placeholder, spec in params.items():
        kind = spec[1]
        value = spec[0]

        if kind == "number":
            f = float(value)
            literal = str(int(f)) if f == int(f) else str(f)
        elif kind == "duration":
            unit = spec[2]
            literal = f"INTERVAL '{value} {unit}'"
        elif kind == "string":
            escaped = str(value).replace("'", "''")
            literal = f"'{escaped}'"
        elif kind == "bool":
            literal = "TRUE" if value else "FALSE"
        else:
            raise ValueError(f"Unknown parameter kind: {kind!r}")

        sql = sql.replace(f"{{{placeholder}}}", literal)

    return sql


def run_check(
    sql_template: str,
    params: dict[str, tuple],
    datasets: dict[str, str],
    timeout_seconds: float = 30.0,
) -> CheckResult:
    """Run a SQL check template against Parquet datasets via DuckDB.

    The *sql_template* uses ``{placeholder}`` syntax for parameter binding.
    Each dataset is registered as a view named by its key.
    Returns a :class:`CheckResult` whose rows are the query violations.
    """
    t_start = time.perf_counter()

    # --- Validate and substitute ------------------------------------------------
    try:
        cleaned_sql = _validate_sql(sql_template)
        final_sql = _substitute_params(cleaned_sql, params)
    except ValueError:
        raise  # propagate directly; caller sees the message

    # --- DuckDB execution -------------------------------------------------------
    conn = duckdb.connect()

    # Register each Parquet file as a view.
    # DuckDB doesn't support prepared parameters in CREATE VIEW, so we interpolate
    # the path directly after escaping single quotes.
    for name, path in datasets.items():
        safe_path = str(path).replace("'", "''")
        conn.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{safe_path}')")

    timed_out = threading.Event()

    def _interrupt():
        timed_out.set()
        conn.interrupt()

    timer = threading.Timer(timeout_seconds, _interrupt)
    timer.start()
    try:
        # Count total violations first.
        count_sql = f"SELECT COUNT(*) FROM ({final_sql}) _sub"
        try:
            violation_count = conn.execute(count_sql).fetchone()[0]
        except Exception as exc:
            if timed_out.is_set():
                return CheckResult(
                    violation_count=0,
                    affected_count=0,
                    sample_rows=[],
                    elapsed_seconds=time.perf_counter() - t_start,
                    error="timeout",
                )
            return CheckResult(
                violation_count=0,
                affected_count=0,
                sample_rows=[],
                elapsed_seconds=time.perf_counter() - t_start,
                error=str(exc),
            )

        # Fetch up to 20 sample rows.
        try:
            rel = conn.execute(final_sql)
            columns = [desc[0] for desc in rel.description]
            raw_rows = rel.fetchmany(20)
        except Exception as exc:
            if timed_out.is_set():
                return CheckResult(
                    violation_count=0,
                    affected_count=0,
                    sample_rows=[],
                    elapsed_seconds=time.perf_counter() - t_start,
                    error="timeout",
                )
            return CheckResult(
                violation_count=0,
                affected_count=0,
                sample_rows=[],
                elapsed_seconds=time.perf_counter() - t_start,
                error=str(exc),
            )
    finally:
        timer.cancel()

    sample_rows = [dict(zip(columns, row)) for row in raw_rows]

    return CheckResult(
        violation_count=violation_count,
        affected_count=violation_count,
        sample_rows=sample_rows,
        elapsed_seconds=time.perf_counter() - t_start,
    )
