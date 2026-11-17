"""Database driver and ORM integrations for PGRetry.

Provides:
- sqlalchemy.py: SQLAlchemy AsyncSession integration
  (SQLAlchemySessionAdapter, SQLAlchemyTransactionRunner, run_sqlalchemy_transaction)
- asyncpg.py: asyncpg driver integration
  (AsyncpgConnectionAdapter, AsyncpgTransactionRunner, run_asyncpg_transaction)

Driver integrations are imported conditionally so that core PGRetry remains
a zero-dependency library when drivers are not installed.
"""

from __future__ import annotations

from typing import Any

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

__all__ = [
    # sqlalchemy
    "SQLAlchemySessionAdapter",
    "SQLAlchemyQueryExecutor",
    "SQLAlchemyTransactionRunner",
    "extract_sqlalchemy_sqlstate",
    "run_sqlalchemy_transaction",
    # asyncpg
    "AsyncpgConnectionAdapter",
    "AsyncpgQueryExecutor",
    "AsyncpgTransactionRunner",
    "extract_asyncpg_sqlstate",
    "run_asyncpg_transaction",
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
