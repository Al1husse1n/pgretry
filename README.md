# PGRetry: PostgreSQL Concurrency & Retry Toolkit for Python

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![PyPI version](https://img.shields.io/pypi/v/pgretry.svg)](https://pypi.org/project/pgretry/)
[![CI](https://github.com/Al1husse1n/pgretry/actions/workflows/ci.yml/badge.svg)](https://github.com/Al1husse1n/pgretry/actions)
[![Dependencies](https://img.shields.io/badge/dependencies-zero_core-success.svg)](#installation)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PGRetry** is a zero-dependency, production-grade concurrency resilience and whole-transaction retry toolkit for PostgreSQL applications written in async Python.

---

## The Problem

When running concurrent PostgreSQL workloads—especially under `SERIALIZABLE` or `REPEATABLE READ` isolation—transaction aborts are not unexpected bugs; they are PostgreSQL's primary concurrency control signal.

When a conflict occurs, PostgreSQL aborts the transaction with SQLSTATE **`40001`** (serialization failure) or **`40P01`** (deadlock detected) and places the connection into an `InFailedSqlTransaction` state. Retrying a single failing statement is impossible: the entire transaction boundary must be rolled back, paced with backoff jitter, and **re-executed from the very beginning**. Standard database drivers leave this complex orchestration entirely to the application.

---

## Quick Start

### 1. Functional Style (`asyncpg`)

Execute an entire financial transfer inside an atomic, retry-safe transaction boundary:

```python
import asyncpg
from pgretry import run_asyncpg_transaction, RetryPolicy

async def transfer_funds(conn: asyncpg.Connection, sender_id: int, recipient_id: int, amount: int):
    async def _tx(c: asyncpg.Connection):
        # 1. Deduct sender
        balance = await c.fetchval(
            "UPDATE accounts SET balance = balance - $1 WHERE id = $2 RETURNING balance",
            amount, sender_id,
        )
        if balance < 0:
            raise ValueError("Insufficient balance")

        # 2. Credit recipient
        await c.execute("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, recipient_id)
        return balance

    # Automatically retries whole transaction if 40001 / 40P01 occurs
    return await run_asyncpg_transaction(
        connection=conn,
        operation=_tx,
        policy=RetryPolicy(max_attempts=5, base_delay=0.02),
    )
```

### 2. Declarative Decorator Style

Decorate any async function to wrap its execution in automatic whole-transaction retries:

```python
from pgretry import transaction

@transaction(max_attempts=3, base_delay=0.05)
async def create_order(user_id: int, item_id: int):
    # Automatically retried from line 1 on concurrency aborts
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE inventory SET stock = stock - 1 WHERE id = $1", item_id)
            await conn.execute("INSERT INTO orders (user_id, item_id) VALUES ($1, $2)", user_id, item_id)
```

---

## Why Not Tenacity or a Hand-Rolled Loop?

Generic retry libraries (like Tenacity) are designed for stateless operations (like HTTP requests). Using them for database transactions introduces subtle production bugs:

| Concern | Generic Retry Loops (`tenacity` / `while`) | PGRetry |
| :--- | :--- | :--- |
| **Transaction State** | Sleeps while holding connection in `InFailedSqlTransaction`, keeping locks active. | **Rollback-Before-Sleep:** Issues an explicit `ROLLBACK` immediately, before calculating backoff. |
| **Retry Scope** | Retries only the failing SQL line; leaves earlier statements in an invalid state. | **Whole-Transaction Replay:** Re-executes the entire callable from line 1 with a clean snapshot. |
| **Error Precision** | Blindly catches `Exception` (retrying unique violations `23505` that can never succeed). | **SQLSTATE-Aware:** Selectively retries `40001` & `40P01`; fails fast on constraint violations. |
| **Commit Ambiguity** | Retries if a network drop occurs during `COMMIT`, risking duplicate operations. | **Ambiguous Commit Safety:** Refuses to retry commit-phase failures where state is uncertain. |
| **Observability** | Only captures exception strings. | **Engine Diagnostics:** Automatically queries `pg_locks` and `pg_stat_activity` on contention. |

---

## Features

- **Zero Core Dependencies:** Pure Python implementation with zero third-party dependencies required.
- **SQLSTATE Classification:** Natively inspects `error.sqlstate` across `asyncpg`, `SQLAlchemy`, and `psycopg3`.
- **Full-Jitter Exponential Backoff:** Equal-probability Decorrelated Full Jitter to avoid thundering-herd spikes.
- **Driver Agnostic:** Protocol-based architecture with first-class support for `asyncpg`, `SQLAlchemy` (`AsyncSession`), and custom adapters (`psycopg3`).
- **PostgreSQL Observability:** Dedicated diagnostic collectors for `pg_stat_activity` and `pg_locks` wait-queues.
- **Credential Sanitization:** Automated redactor masks sensitive tokens, passwords, and connection DSNs in logs.
- **Telemetry Metrics:** In-memory thread-safe metrics collector capturing attempt counts, durations, and conflict rates.
- **Strict Typing:** 100% type-annotated with PEP 561 `py.typed` marker; passes strict `mypy` and `pyright`.

---

## Installation

```bash
pip install pgretry
```

Compatible with **Python 3.11, 3.12, and 3.13+**.

---

## Safety Notes

1. **Operations Must Be Idempotent:** Any callable passed to `pgretry` may execute multiple times up to `max_attempts`.
2. **No External Side Effects Inside Retries:** Do not send emails, trigger webhooks, or charge credit cards inside the transactional callable. Defer external actions until after the transaction commits (e.g. using an transactional outbox pattern).
3. **Ambiguous Commit Outcomes:** If a network failure occurs while issuing `COMMIT`, `pgretry` intentionally does **not** retry because PostgreSQL may have already committed the changes.
4. **Keep Transactions Short:** Long-running transactions hold locks and increase contention under `SERIALIZABLE` isolation.
5. **Bounded Retries:** Always configure a sensible `max_attempts` limit (default: 3) to prevent runaway retry loops under extreme load.

---

## Known Limitations

- **Async Runtimes Only:** Engineered strictly for modern asynchronous Python (`asyncio`); synchronous database drivers are not supported.
- **SSI Conflicts vs Heavyweight Locks:** PostgreSQL tracks SSI conflicts (`40001`) via in-memory SIREAD predicate locks that do not appear as blocking locks in `pg_locks`.
- **Point-in-Time Diagnostics:** Diagnostic snapshots represent engine state immediately after failure; short-lived locks may release before diagnostics run.

See [docs/limitations.md](https://github.com/Al1husse1n/pgretry/blob/main/docs/limitations.md) for the complete 10-point architectural limitation review.

---

## Documentation

Comprehensive guides and deep dives are available in the `docs/` directory:

| Guide | Description |
| :--- | :--- |
| [How It Works](https://github.com/Al1husse1n/pgretry/blob/main/docs/how-it-works.md) | Lifecycle flowcharts, whole-transaction replay architecture, and why context managers cannot retry. |
| [Retry Policy & Jitter](https://github.com/Al1husse1n/pgretry/blob/main/docs/retry-policy.md) | `RetryPolicy` configuration options, backoff formulas, and full-jitter math. |
| [Error Classification](https://github.com/Al1husse1n/pgretry/blob/main/docs/error-classification.md) | PostgreSQL SQLSTATE categories, retryable vs fail-fast codes, and custom extractors. |
| [Driver Integrations](https://github.com/Al1husse1n/pgretry/blob/main/docs/integrations.md) | Deep guides for SQLAlchemy (`AsyncSession`), asyncpg, custom adapters (psycopg 3), and FastAPI. |
| [Engine Diagnostics](https://github.com/Al1husse1n/pgretry/blob/main/docs/diagnostics.md) | Lock contention analysis (`pg_locks`), session monitoring (`pg_stat_activity`), and blocking chains. |
| [Observability & Telemetry](https://github.com/Al1husse1n/pgretry/blob/main/docs/observability.md) | Structured logging, credential redaction, telemetry metrics snapshots, and attempt tracking. |
| [Public API Reference](https://github.com/Al1husse1n/pgretry/blob/main/docs/api-reference.md) | Complete reference of exported symbols, classes, protocols, and methods. |
| [Testing Guide](https://github.com/Al1husse1n/pgretry/blob/main/docs/testing.md) | Executing unit tests, Docker Compose testing, integration test setup, and CI architecture. |
| [Known Limitations](https://github.com/Al1husse1n/pgretry/blob/main/docs/limitations.md) | 10-point architectural boundary and operational constraint review. |

---

## Benchmark

<!-- TODO: N concurrent SERIALIZABLE workers, with vs. without PGRetry -->
*Benchmark suite comparing throughput, serialization conflict resolution, and latency under high concurrency is currently in progress.*

---

## Contributing

Contributions, bug reports, and pull requests are welcome! See [CONTRIBUTING.md](https://github.com/Al1husse1n/pgretry/blob/main/CONTRIBUTING.md) for development environment setup and pull request guidelines.

---

## License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/Al1husse1n/pgretry/blob/main/LICENSE) file for details.
