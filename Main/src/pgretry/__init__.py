"""PGRetry: PostgreSQL concurrency and retry toolkit for Python applications."""

from __future__ import annotations

from typing import Any

from pgretry.instrumentation import (
    InMemoryMetricsCollector,
    LoggedTransactionEvent,
    MetricsCollector,
    MetricsSnapshot,
    NullMetricsCollector,
    TransactionEventType,
    TransactionLogger,
    sanitize_value,
)
from pgretry.postgres import (
    AuthoritativeBlocking,
    DiagnosticCollector,
    DiagnosticMode,
    DiagnosticReport,
    LockInfo,
    PostgresErrorCategory,
    PostgresErrorDetails,
    SessionActivity,
    build_diagnostic_report,
    fetch_blocking_pids,
    fetch_locks,
    fetch_locks_with_authoritative,
    parse_postgres_error,
)
from pgretry.retry import (
    ClassificationResult,
    ErrorCategory,
    RetryPolicy,
    calculate_backoff,
    classify_error,
    extract_sqlstate,
    is_retryable,
)
from pgretry.transaction import (
    AttemptRecord,
    NullTransactionAdapter,
    TransactionAdapter,
    TransactionContext,
    TransactionResult,
    TransactionRunner,
    get_current_context,
    transaction,
    transactional,
)

# Optional driver integrations (imported conditionally so core remains zero-dependency)
try:
    from pgretry.integrations.asyncpg import (
        AsyncpgConnectionAdapter,
        AsyncpgQueryExecutor,
        AsyncpgTransactionRunner,
        extract_asyncpg_sqlstate,
        run_asyncpg_transaction,
    )
except ImportError:
    pass

try:
    from pgretry.integrations.sqlalchemy import (
        SQLAlchemyQueryExecutor,
        SQLAlchemySessionAdapter,
        SQLAlchemyTransactionRunner,
        extract_sqlalchemy_sqlstate,
        run_sqlalchemy_transaction,
    )
except ImportError:
    pass

__version__ = "0.1.0"

__all__ = [
    # Retry subsystem
    "RetryPolicy",
    "calculate_backoff",
    "classify_error",
    "is_retryable",
    "extract_sqlstate",
    "ClassificationResult",
    "ErrorCategory",
    # Transaction subsystem
    "TransactionRunner",
    "TransactionAdapter",
    "NullTransactionAdapter",
    "TransactionResult",
    "TransactionContext",
    "AttemptRecord",
    "get_current_context",
    "transaction",
    "transactional",
    # PostgreSQL subsystem
    "PostgresErrorDetails",
    "PostgresErrorCategory",
    "parse_postgres_error",
    "SessionActivity",
    "LockInfo",
    "AuthoritativeBlocking",
    "fetch_locks",
    "fetch_blocking_pids",
    "fetch_locks_with_authoritative",
    "DiagnosticReport",
    "DiagnosticMode",
    "DiagnosticCollector",
    "build_diagnostic_report",
    # Instrumentation subsystem
    "TransactionLogger",
    "LoggedTransactionEvent",
    "TransactionEventType",
    "sanitize_value",
    "MetricsCollector",
    "InMemoryMetricsCollector",
    "NullMetricsCollector",
    "MetricsSnapshot",
    # Integrations
    "SQLAlchemySessionAdapter",
    "SQLAlchemyQueryExecutor",
    "SQLAlchemyTransactionRunner",
    "run_sqlalchemy_transaction",
    "extract_sqlalchemy_sqlstate",
    "AsyncpgConnectionAdapter",
    "AsyncpgQueryExecutor",
    "AsyncpgTransactionRunner",
    "run_asyncpg_transaction",
    "extract_asyncpg_sqlstate",
]


def __getattr__(name: str) -> Any:
    if name in {
        "AsyncpgConnectionAdapter",
        "AsyncpgQueryExecutor",
        "AsyncpgTransactionRunner",
        "extract_asyncpg_sqlstate",
        "run_asyncpg_transaction",
    }:
        raise ImportError(f"'{name}' requires asyncpg. Install it via: pip install asyncpg")
    if name in {
        "SQLAlchemySessionAdapter",
        "SQLAlchemyQueryExecutor",
        "SQLAlchemyTransactionRunner",
        "extract_sqlalchemy_sqlstate",
        "run_sqlalchemy_transaction",
    }:
        raise ImportError(f"'{name}' requires sqlalchemy. Install it via: pip install sqlalchemy")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
