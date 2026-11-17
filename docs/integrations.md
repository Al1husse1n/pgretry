# Driver Integrations & Frameworks

## Supported Integrations

PGRetry provides dedicated, tested adapters for the two primary asynchronous database toolkits in Python: **SQLAlchemy** and **asyncpg**.

### SQLAlchemy (`AsyncSession`)

The `SQLAlchemySessionAdapter` bridges an active `sqlalchemy.ext.asyncio.AsyncSession` to PGRetry's `TransactionAdapter` protocol.

* `begin()`: Calls `await session.begin()`. If the session is already in an active transaction (`session.in_transaction()`), raises `RuntimeError`.
* `commit()`: Calls `await session.commit()`.
* `rollback()`: Calls `await session.rollback()`. PGRetry does not call `expunge_all()`; pending objects in the caller's session are left as-is after rollback.

#### Helper: `run_sqlalchemy_transaction`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update
from pgretry import run_sqlalchemy_transaction, RetryPolicy

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost:5432/mydb")
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def debit_account(session: AsyncSession, account_id: int, amount: float):
    # This callable is re-run from the top if a 40001/40P01 occurs
    async def _tx_operation(s: AsyncSession):
        stmt = select(Account).where(Account.id == account_id).with_for_update()
        account = (await s.execute(stmt)).scalar_one()

        if account.balance < amount:
            raise ValueError("Insufficient balance")

        account.balance -= amount
        return account.balance

    async with session_factory() as session:
        return await run_sqlalchemy_transaction(
            session=session,
            operation=_tx_operation,
            policy=RetryPolicy(max_attempts=3, base_delay=0.05),
            metadata={"transaction_id": f"debit-{account_id}"},
        )
```

### asyncpg (`asyncpg.Connection`)

The `AsyncpgConnectionAdapter` integrates directly with raw `asyncpg.Connection` instances.

* `begin()`: Creates and starts an `asyncpg.transaction.Transaction` (`conn.transaction()`). If the connection is already in an active transaction (`conn.is_in_transaction()`), raises `RuntimeError`.
* `commit()`: Commits the active transaction boundary.
* `rollback()`: Rolls back the active transaction boundary.

### Session and connection ownership (v0.1)

* **SQLAlchemy:** PGRetry owns the transaction it starts. If your `AsyncSession` is already in a transaction, PGRetry raises `RuntimeError`. Wrap your own boundary around a fresh session.
* **asyncpg:** PGRetry owns the transaction it starts on the connection you pass. If the connection is already in a transaction, PGRetry raises `RuntimeError`. The correct pool pattern is:
  ```python
  async with pool.acquire() as conn:
      await run_asyncpg_transaction(conn, operation)
  ```
  A pool-aware convenience helper is planned for v0.2.

#### Helper: `run_asyncpg_transaction`

```python
import asyncpg
from pgretry import run_asyncpg_transaction, RetryPolicy


async def transfer_credits(
    conn: asyncpg.Connection, sender_id: int, recipient_id: int, credits: int
):
    async def _tx_operation(c: asyncpg.Connection):
        # 1. Deduct sender
        sender_balance = await c.fetchval(
            "UPDATE users SET credits = credits - $1 WHERE id = $2 RETURNING credits",
            credits,
            sender_id,
        )
        if sender_balance < 0:
            raise ValueError("Sender has insufficient credits")

        # 2. Credit recipient
        await c.execute(
            "UPDATE users SET credits = credits + $1 WHERE id = $2", credits, recipient_id
        )
        return sender_balance

    return await run_asyncpg_transaction(
        connection=conn,
        operation=_tx_operation,
        policy=RetryPolicy(max_attempts=5, base_delay=0.02),
        metadata={"transaction_id": f"transfer-{sender_id}-to-{recipient_id}"},
    )
```

### Custom Driver Adapters (e.g. `psycopg3`)

PGRetry is deliberately decoupled from any single database driver via the `@runtime_checkable` `TransactionAdapter` protocol. If you use a driver that does not have a bundled helper—such as **psycopg 3 (`psycopg.AsyncConnection`)**, custom connection pools, or proxy wrappers—you can write your own adapter in ~20 lines of code.

#### Why and When to Create a Custom Adapter

* **Driver Flexibility without Waiting for Releases:** You do not need to wait for PGRetry to bundle support for your driver or internal connection abstraction.
* **Automatic SQLSTATE Classification:** PGRetry's error classifier natively inspects exception hierarchies from `psycopg` and `psycopg2` (`error.sqlstate` / `error.pgcode`). Concurrency aborts (`40001` serialization failure, `40P01` deadlock detected) are automatically classified as retryable without writing a custom error extractor.
* **Fail-Fast Validation:** `TransactionRunner` validates that your adapter implements `TransactionAdapter` via runtime `isinstance` checks at initialization, raising `TypeError` immediately if an unadapted connection is passed.

#### Minimal Example: `psycopg 3` Async Adapter

```python
import contextlib
from typing import Any
import psycopg
from pgretry.transaction import TransactionAdapter, TransactionRunner

class PsycopgConnectionAdapter(TransactionAdapter):
    """Adapts a psycopg 3 AsyncConnection to PGRetry's TransactionAdapter protocol."""

    def __init__(self, connection: psycopg.AsyncConnection[Any]) -> None:
        self._connection = connection
        self._tx: psycopg.AsyncTransaction | None = None

    async def begin(self) -> None:
        """Create and start a new transaction boundary on the connection."""
        if self._tx is not None:
            await self.rollback()
        self._tx = self._connection.transaction()
        await self._tx.__aenter__()

    async def commit(self) -> None:
        """Commit the active transaction boundary."""
        if self._tx is not None:
            await self._tx.__aexit__(None, None, None)
            self._tx = None

    async def rollback(self) -> None:
        """Roll back the active transaction boundary."""
        if self._tx is not None:
            with contextlib.suppress(Exception):
                await self._tx.__aexit__(Exception, Exception("PGRetry rollback"), None)
            self._tx = None

# Pass directly to TransactionRunner:
# runner = TransactionRunner(adapter=PsycopgConnectionAdapter(conn))
# result = await runner.run(my_async_callable)
```

> [!TIP]
> **Complete Runnable Example:** See [examples/custom_adapter_psycopg.py](examples/custom_adapter_psycopg.py) for a complete, self-contained demonstration including database table creation, balance transfers, and automated retries using psycopg 3.

---

---

## Declarative Decorators (`@transaction`, `@transactional`)

PGRetry provides `@transaction` (and its alias `@transactional`) to wrap async functions declaratively.

```python
from pgretry import transaction


# Basic usage (defaults to RetryPolicy())
@transaction
async def get_user_profile(user_id: int): ...


# Customized policy overrides
@transaction(max_attempts=3, base_delay=0.1, max_delay=1.0, jitter=True)
async def update_user_balance(user_id: int, new_balance: float): ...
```

### Injecting Dependencies into Decorators

You can inject pre-configured components (such as adapters, loggers, or runners) directly into the decorator:

```python
from pgretry import transaction, TransactionRunner, RetryPolicy

custom_runner = TransactionRunner(
    policy=RetryPolicy(max_attempts=4, base_delay=0.02),
    logger=my_logger,
    metrics=my_metrics,
)


@transaction(runner=custom_runner)
async def execute_order(order_id: str): ...
```

The decorator preserves the original function's signature and docstrings via `functools.wraps`, and attaches the runner instance as `.__pgretry_runner__`.

---

---

## FastAPI Integration Example

In FastAPI applications, database sessions are typically managed via dependency injection. Here is a production pattern integrating PGRetry, SQLAlchemy `AsyncSession`, and FastAPI routes:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from pgretry import (
    RetryPolicy,
    TransactionRunner,
    SQLAlchemySessionAdapter,
    InMemoryMetricsCollector,
    TransactionLogger,
    run_sqlalchemy_transaction,
)

# 1. Configure PostgreSQL Engine with SERIALIZABLE isolation
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/banking_db"
engine = create_async_engine(
    DATABASE_URL,
    isolation_level="SERIALIZABLE",  # Explicitly enable serializable snapshot isolation
    pool_size=20,
)
session_factory = async_sessionmaker(engine, expire_on_commit=False)

# 2. Shared PGRetry Telemetry
metrics = InMemoryMetricsCollector()
logger = TransactionLogger(enabled=True)
retry_policy = RetryPolicy(max_attempts=3, base_delay=0.05, max_delay=0.5)

app = FastAPI(title="PGRetry Banking API")


async def get_db_session() -> AsyncSession:
    async with session_factory() as session:
        yield session


class TransferRequest(BaseModel):
    account_from: int
    account_to: int
    amount: float


@app.post("/transfer")
async def transfer_money(
    req: TransferRequest,
    session: AsyncSession = Depends(get_db_session),
):
    # Encapsulate the full transfer logic in a transactional callable
    async def _do_transfer(s: AsyncSession):
        # 1. Read sender
        res_from = await s.execute(select(Account).where(Account.id == req.account_from))
        acc_from = res_from.scalar_one_or_none()
        if not acc_from or acc_from.balance < req.amount:
            raise ValueError("Insufficient funds or invalid sender account")

        # 2. Read recipient
        res_to = await s.execute(select(Account).where(Account.id == req.account_to))
        acc_to = res_to.scalar_one_or_none()
        if not acc_to:
            raise ValueError("Invalid recipient account")

        # 3. Update balances
        acc_from.balance -= req.amount
        acc_to.balance += req.amount
        return {"from_balance": acc_from.balance, "to_balance": acc_to.balance}

    try:
        result = await run_sqlalchemy_transaction(
            session=session,
            operation=_do_transfer,
            policy=retry_policy,
            metadata={"transaction_id": f"tx-{req.account_from}-{req.account_to}"},
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

> [!IMPORTANT]
> **PostgreSQL Isolation Level Requirement:**
> To trigger and test serialization failures (`40001`), PostgreSQL must run in `SERIALIZABLE` (or `REPEATABLE READ`) mode. By default, PostgreSQL connections use `READ COMMITTED`, which uses statement-level snapshots and avoids serialization conflicts (though deadlocks `40P01` can still occur). Configure `isolation_level="SERIALIZABLE"` on your SQLAlchemy engine or asyncpg connection.

---
