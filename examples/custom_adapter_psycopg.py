# pyright: reportMissingImports=false
"""PGRetry Custom Adapter Example: psycopg 3 (psycopg).

Demonstrates how to build a custom TransactionAdapter for database drivers
that are not bundled directly into PGRetry's core (such as psycopg 3).

When and Why to Create a Custom Adapter:
---------------------------------------
PGRetry ships with built-in adapters for SQLAlchemy (`AsyncSession`) and
asyncpg (`Connection`). However, Python's async ecosystem includes other drivers
like psycopg 3 (`psycopg.AsyncConnection`), third-party connection pools, or
custom connection wrappers.

Instead of requiring developers to wait for official driver integration releases,
PGRetry exposes the `@runtime_checkable` `TransactionAdapter` Protocol:
    - `async def begin(self) -> None`: Starts a new transaction boundary.
    - `async def commit(self) -> None`: Commits the active transaction boundary.
    - `async def rollback(self) -> None`: Rolls back the active transaction boundary.

Any object implementing these three async methods satisfies `TransactionAdapter`.
`TransactionRunner` automatically coordinates whole-transaction retries against
this interface, and verifies it at initialization using `isinstance` checks.

Furthermore, PGRetry's error classification engine already natively inspects
`psycopg` exception hierarchies (via `error.sqlstate` / `error.pgcode`), so
transient concurrency errors (40001 serialization failures, 40P01 deadlocks)
are retried automatically out-of-the-box without requiring custom error extractors.

To run this example:
    pip install "psycopg[binary]>=3.1"
    export PGRETRY_TEST_DSN="postgresql://postgres:postgres@localhost:5432/postgres"
    python examples/custom_adapter_psycopg.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from pgretry import RetryPolicy
from pgretry.transaction import TransactionAdapter, TransactionRunner

if TYPE_CHECKING:
    import psycopg
else:
    try:
        import psycopg
    except ImportError:
        psycopg = None

T = TypeVar("T")


class PsycopgConnectionAdapter(TransactionAdapter):
    """Adapts a psycopg 3 AsyncConnection to PGRetry's TransactionAdapter protocol.

    Manages transaction lifecycle by entering and exiting psycopg's AsyncTransaction
    context manager across retry attempts.
    """

    def __init__(self, connection: Any) -> None:
        """Initialize adapter with an active psycopg AsyncConnection."""
        self._connection = connection
        self._tx: Any = None

    @property
    def connection(self) -> Any:
        """Return the underlying psycopg AsyncConnection."""
        return self._connection

    async def begin(self) -> None:
        """Create and start a new transaction boundary on the connection."""
        if self._tx is not None:
            await self.rollback()
        self._tx = self._connection.transaction()
        await self._tx.__aenter__()

    async def commit(self) -> None:
        """Commit current transaction boundary."""
        if self._tx is not None:
            await self._tx.__aexit__(None, None, None)
            self._tx = None

    async def rollback(self) -> None:
        """Roll back current transaction boundary."""
        if self._tx is not None:
            with contextlib.suppress(Exception):
                await self._tx.__aexit__(Exception, Exception("PGRetry rollback"), None)
            self._tx = None


async def run_psycopg_transaction(
    connection: Any,
    operation: Callable[[Any], Awaitable[T]],
    policy: RetryPolicy | None = None,
) -> T:
    """Execute an async operation within an atomic, retry-safe psycopg transaction."""
    adapter = PsycopgConnectionAdapter(connection)
    runner = TransactionRunner(adapter=adapter, policy=policy)
    return await runner.run(lambda: operation(connection))


async def main() -> None:
    if psycopg is None:
        print(
            "Error: psycopg 3 is not installed.\n"
            "Install it via: pip install 'psycopg[binary]>=3.1'",
            file=sys.stderr,
        )
        sys.exit(1)

    dsn = os.environ.get("PGRETRY_TEST_DSN") or os.environ.get("PGSHIELD_TEST_DSN")
    if not dsn:
        print("Error: PGRETRY_TEST_DSN environment variable is not set.", file=sys.stderr)
        print(
            "Example: export PGRETRY_TEST_DSN="
            "'postgresql://postgres:postgres@localhost:5432/postgres'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Connect using psycopg 3's asynchronous connection API
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        # 1. Prepare table and sample balances
        async with conn.cursor() as cur:
            await cur.execute(
                "CREATE TABLE IF NOT EXISTS demo_psycopg_accounts "
                "(id INT PRIMARY KEY, balance INT);"
            )
            await cur.execute("TRUNCATE TABLE demo_psycopg_accounts;")
            await cur.execute(
                "INSERT INTO demo_psycopg_accounts (id, balance) VALUES (1, 1000), (2, 500);"
            )
        await conn.commit()

        # 2. Define business logic for transfer
        async def transfer(c: Any) -> None:
            amount = 200
            async with c.cursor() as cur:
                await cur.execute(
                    "UPDATE demo_psycopg_accounts SET balance = balance - %s WHERE id = %s;",
                    (amount, 1),
                )
                await cur.execute(
                    "UPDATE demo_psycopg_accounts SET balance = balance + %s WHERE id = %s;",
                    (amount, 2),
                )

        # 3. Execute with whole-transaction automatic retries via custom adapter
        await run_psycopg_transaction(conn, transfer)

        # 4. Verify committed balances
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT balance FROM demo_psycopg_accounts WHERE id = 1;"
            )
            row1 = await cur.fetchone()
            await cur.execute(
                "SELECT balance FROM demo_psycopg_accounts WHERE id = 2;"
            )
            row2 = await cur.fetchone()
            b1 = row1[0] if row1 else 0
            b2 = row2[0] if row2 else 0
            print(f"Transfer successful! Account 1: ${b1}, Account 2: ${b2}")

            await cur.execute("DROP TABLE demo_psycopg_accounts;")
        await conn.commit()


if __name__ == "__main__":
    asyncio.run(main())
