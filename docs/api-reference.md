# Public API Reference

## Public API Reference

All primary symbols are exported at the root `pgretry` package level:

```python
import pgretry
```

### Core Symbols Exported in `pgretry.__all__`

| Symbol | Category | Description |
| :--- | :--- | :--- |
| `RetryPolicy` | Retry | Immutable configuration for retries, delays, and SQLSTATEs. |
| `calculate_backoff` | Retry | Calculates exponential backoff with full jitter for an attempt. |
| `classify_error` | Retry | Inspects an exception and returns a structured `ClassificationResult`. |
| `is_retryable` | Retry | Convenience boolean check for error retryability. |
| `extract_sqlstate` | Retry | Extracts a 5-character SQLSTATE string across diverse exception types. |
| `ClassificationResult`| Retry | Dataclass storing retry decision, SQLSTATE, category, and reason. |
| `ErrorCategory` | Retry | Enum for categorized errors (`SERIALIZATION_FAILURE`, `DEADLOCK_DETECTED`, etc.). |
| `TransactionRunner` | Transaction | Central orchestrator executing whole-transaction retries. |
| `TransactionAdapter` | Transaction | Protocol for transaction boundaries (`begin`, `commit`, `rollback`). |
| `NullTransactionAdapter`| Transaction | No-op adapter for transactions managed internally. |
| `TransactionResult` | Transaction | Return container storing value, attempts, duration, and history. |
| `TransactionContext`| Transaction | Live execution metadata available via `get_current_context()`. |
| `AttemptRecord` | Transaction | Immutable historical record of a single transaction attempt. |
| `get_current_context`| Transaction | Retrieves active `TransactionContext` from `contextvars`. |
| `transaction` | Transaction | Decorator wrapping async functions with automatic retries. |
| `transactional` | Transaction | Semantic alias for `transaction`. |
| `PostgresErrorDetails`| PostgreSQL | Normalized dataclass with SQLSTATE, hint, detail, table, and column. |
| `PostgresErrorCategory`| PostgreSQL | Categorization of PostgreSQL errors for diagnostics. |
| `parse_postgres_error`| PostgreSQL | Normalizes driver and ORM exceptions into `PostgresErrorDetails`. |
| `SessionActivity` | PostgreSQL | Dataclass representing a session snapshot from `pg_stat_activity`. |
| `LockInfo` | PostgreSQL | Dataclass representing a lock snapshot from `pg_locks`. |
| `DiagnosticReport` | PostgreSQL | Structured diagnostic report with blocking analysis and recommendations. |
| `DiagnosticMode` | PostgreSQL | Enum controlling diagnostic execution (`OFF`, `ON_FAILURE`, `SAMPLED`, `ALWAYS`). |
| `DiagnosticCollector`| PostgreSQL | Engine for executing diagnostic queries and building reports. |
| `build_diagnostic_report`| PostgreSQL | Factory function assembling a `DiagnosticReport`. |
| `TransactionLogger` | Instrumentation | Structured event logger for transaction lifecycles. |
| `LoggedTransactionEvent`| Instrumentation | Dataclass representing an emitted logging event. |
| `TransactionEventType`| Instrumentation | Enum of lifecycle events (`started`, `committed`, `retry`, etc.). |
| `sanitize_value` | Instrumentation | Recursive redactor for sensitive keys and connection URLs. |
| `MetricsCollector` | Instrumentation | Protocol for recording transaction metrics. |
| `InMemoryMetricsCollector`| Instrumentation | Thread-safe, in-memory implementation of `MetricsCollector`. |
| `NullMetricsCollector`| Instrumentation | Zero-overhead, no-op metrics collector. |
| `MetricsSnapshot` | Instrumentation | Immutable snapshot of aggregated transaction telemetry. |
| `SQLAlchemySessionAdapter`| Integration | Adapts SQLAlchemy `AsyncSession` to `TransactionAdapter`. |
| `SQLAlchemyTransactionRunner`| Integration | Specialized `TransactionRunner` for SQLAlchemy. |
| `run_sqlalchemy_transaction`| Integration | Helper executing a callable with retries on an `AsyncSession`. |
| `extract_sqlalchemy_sqlstate`| Integration | Extracts SQLSTATE from SQLAlchemy `DBAPIError.orig`. |
| `AsyncpgConnectionAdapter`| Integration | Adapts `asyncpg.Connection` to `TransactionAdapter`. |
| `AsyncpgTransactionRunner`| Integration | Specialized `TransactionRunner` for asyncpg. |
| `run_asyncpg_transaction`| Integration | Helper executing a callable with retries on an `asyncpg.Connection`. |
| `extract_asyncpg_sqlstate`| Integration | Extracts SQLSTATE from `asyncpg.PostgresError`. |
| `AsyncpgQueryExecutor`| Integration | Concrete `QueryExecutor` adapter for `asyncpg.Connection`. |
| `SQLAlchemyQueryExecutor`| Integration | Concrete `QueryExecutor` adapter for SQLAlchemy `AsyncSession`. |
| `AuthoritativeBlocking`| PostgreSQL | Dataclass representing authoritative blocking PIDs from `pg_blocking_pids`. |
| `fetch_blocking_pids` | PostgreSQL | Direct inspection of `pg_blocking_pids` for a given backend PID. |
| `fetch_locks_with_authoritative` | PostgreSQL | Queries `pg_locks` and authoritative blocking PIDs simultaneously. |

---
