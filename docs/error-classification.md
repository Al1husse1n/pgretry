# SQLSTATE Classification & Error Normalization

## SQLSTATE-Aware Retry Classification

Blindly retrying every database exception is dangerous. Retrying an integrity violation (such as a duplicate primary key) wastes database resources and masks business logic bugs. 

PGRetry inspects exceptions using PostgreSQL's standard 5-character **SQLSTATE** codes defined in the SQL standard and PostgreSQL documentation.

### Implemented Retryable Codes

By default, PGRetry considers only transient concurrency conflicts retryable:

| SQLSTATE | Error Name | Description | Default Action |
| :--- | :--- | :--- | :--- |
| **`40001`** | `serialization_failure` | Read/write dependency conflict under SSI or snapshot isolation. | **RETRY** with backoff & jitter |
| **`40P01`** | `deadlock_detected` | Deadlock cycle detected in PostgreSQL lock graph. | **RETRY** with backoff & jitter |

### Implemented Non-Retryable Codes (Immediate Fail-Fast)

Deterministic constraint and syntax violations are **never** retried:

| SQLSTATE | Error Name | Reason Not Retried | Default Action |
| :--- | :--- | :--- | :--- |
| **`23505`** | `unique_violation` | Duplicate key violates unique constraint; cannot succeed without data changes. | **FAIL FAST** (Rollback & Raise) |
| **`23503`** | `foreign_key_violation` | Referenced key does not exist; deterministic schema violation. | **FAIL FAST** (Rollback & Raise) |
| **`23514`** | `check_violation` | Row data violates column check constraint. | **FAIL FAST** (Rollback & Raise) |
| **`23502`** | `not_null_violation` | NULL value supplied for NOT NULL column. | **FAIL FAST** (Rollback & Raise) |
| **`42P01`** | `undefined_table` | Table does not exist in schema. | **FAIL FAST** (Rollback & Raise) |

### Direct Classification API

You can use PGRetry's classification logic directly:

```python
from pgretry.retry import classify_error, is_retryable, ErrorCategory

try:
    await session.execute(...)
except Exception as exc:
    result = classify_error(exc)
    print(result.retryable)  # bool (True for 40001, 40P01)
    print(result.sqlstate)  # "40001"
    print(result.category)  # ErrorCategory.SERIALIZATION_FAILURE
    print(result.reason)  # "PostgreSQL SQLSTATE 40001 (serialization_failure) is retryable"
```

---

---

## PostgreSQL Error Normalization

Python applications interact with PostgreSQL through various drivers and abstraction layers (`asyncpg`, `psycopg2`, `psycopg3`, `SQLAlchemy`). Each library represents errors differently:

```text
PostgreSQL Server
       │ (Emits error wire protocol with 5-char SQLSTATE)
       ▼
Database Driver (asyncpg.PostgresError / psycopg.Error)
       │ (Exposes .sqlstate or .pgcode)
       ▼
SQLAlchemy Layer (sqlalchemy.exc.DBAPIError / OperationalError)
       │ (Wraps driver exception inside .orig)
       ▼
PGRetry Error Normalizer (pgretry.postgres.errors)
       │ (Inspects .sqlstate, .pgcode, .orig, __cause__, __context__)
       ▼
PostgresErrorDetails (Unified, driver-agnostic dataclass)
```

### `PostgresErrorDetails`

The `parse_postgres_error()` function introspects any exception without requiring direct imports of database drivers, returning a normalized `PostgresErrorDetails` dataclass:

```python
from pgretry.postgres import parse_postgres_error

details = parse_postgres_error(error)

print(details.sqlstate)  # e.g. "40001"
print(details.category)  # PostgresErrorCategory.SERIALIZATION_FAILURE
print(details.message)  # Primary error message string
print(details.detail)  # Auxiliary PostgreSQL detail string (if present)
print(details.hint)  # PostgreSQL hint string (if present)
print(details.table_name)  # Table name if relation/constraint error
print(details.column_name)  # Column name if applicable
print(details.constraint_name)  # Constraint name if applicable
print(details.driver_error_type)  # Name of underlying driver exception class
```

---
