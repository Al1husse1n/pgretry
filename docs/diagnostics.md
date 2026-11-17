# PostgreSQL Engine Diagnostics

## Diagnostics Subsystem & QueryExecutor

When a concurrency failure occurs in production, understanding *why* it happened is challenging. PGRetry includes a dedicated diagnostic subsystem to capture and analyze PostgreSQL engine state at the moment of failure.

### Application vs. Diagnostic Execution

It is essential to understand the distinction between application transactions and diagnostic queries:

```text
┌──────────────────────────────────────────────────────────┐
│ Application Execution                                   │
│  - Runs business SQL (SELECT, INSERT, UPDATE, DELETE)    │
│  - Executes inside an explicit transaction boundary     │
│  - Fails with 40001 / 40P01 -> Aborts and rolls back    │
└──────────────────────────────────────────────────────────┘
                            vs.
┌──────────────────────────────────────────────────────────┐
│ Diagnostic Execution                                     │
│  - Runs read-only administrative queries                 │
│  - Queries pg_stat_activity and pg_locks                 │
│  - MUST NOT run inside an aborted transaction block      │
└──────────────────────────────────────────────────────────┘
```

### The `QueryExecutor` Protocol

PGRetry defines a generic, runtime-checkable protocol for running read-only diagnostic SQL:

```python
from typing import Any, Mapping, Optional, Protocol, Sequence


class QueryExecutor(Protocol):
    async def execute_query(
        self, sql: str, params: Optional[Sequence[Any]] = None
    ) -> Sequence[Mapping[str, Any]]:
        """Execute a SQL query and return rows as dictionaries or mapping objects."""
        ...
```

#### Concrete `QueryExecutor` Adapters

PGRetry provides pre-packaged concrete `QueryExecutor` adapters for both asyncpg and SQLAlchemy:

* **`AsyncpgQueryExecutor`** (`pgretry.integrations.asyncpg` or `pgretry`):
  Wraps an `asyncpg.Connection` and returns plain Python dictionaries:
  ```python
  from pgretry import AsyncpgQueryExecutor

  executor = AsyncpgQueryExecutor(conn)
  rows = await executor.execute_query("SELECT 1 AS num")
  ```

* **`SQLAlchemyQueryExecutor`** (`pgretry.integrations.sqlalchemy` or `pgretry`):
  Wraps a SQLAlchemy `AsyncSession` and returns row mappings:
  ```python
  from pgretry import SQLAlchemyQueryExecutor

  executor = SQLAlchemyQueryExecutor(session)
  rows = await executor.execute_query("SELECT 1 AS num")
  ```

### Dedicated Diagnostic Connections

The recommended production pattern is to provide a dedicated connection (or small diagnostic connection pool) via `executor_override`:

```python
import asyncpg
from pgretry import AsyncpgQueryExecutor, DiagnosticCollector, DiagnosticMode

# Configure collector with dedicated diagnostic connection or pool
diag_conn = await asyncpg.connect("postgresql://...")
executor = AsyncpgQueryExecutor(diag_conn)

diagnostics = DiagnosticCollector(
    mode=DiagnosticMode.ON_FAILURE,
    executor=executor,
)
```

---

---

## Active Session Inspection (`pg_stat_activity`)

The `postgres/activity.py` module inspects PostgreSQL backend processes. It queries `pg_stat_activity` while excluding the current diagnostic backend session (`pid <> pg_backend_pid()`).

### `SessionActivity` Dataclass

Each active session is parsed into an immutable `SessionActivity` instance:

```python
@dataclass(frozen=True, slots=True)
class SessionActivity:
    pid: int
    database: Optional[str]
    username: Optional[str]
    application_name: Optional[str]
    client_addr: Optional[str]
    state: Optional[str]  # "active", "idle in transaction", "idle"
    query_start: Optional[datetime | str]
    xact_start: Optional[datetime | str]
    wait_event_type: Optional[str]  # "Lock", "IO", "LWLock", "Client"
    wait_event: Optional[str]  # e.g. "relation", "tuple", "ClientRead"
    query_snippet: Optional[str]  # Truncated query (only if explicitly enabled)
```

### Convenient Diagnostic Properties

* `is_waiting_on_lock`: Returns `True` if `wait_event_type == "Lock"`.
* `is_idle_in_transaction`: Returns `True` if `state == "idle in transaction"` (a primary culprit for holding row locks and causing lock queues).

### Query Snippet Security Toggle

To prevent sensitive user data or credentials from leaking into diagnostic outputs, `include_query_snippet` is `False` by default. When explicitly set to `True`, PGRetry extracts only the first 120 characters via `LEFT(query, 120)`.

---

---

## Lock Contention Analysis (`pg_locks` & `pg_blocking_pids`)

The `postgres/locks.py` module parses PostgreSQL's active lock table, joins relation and schema names from `pg_class` and `pg_namespace`, and analyzes lock contention.

### Two Diagnostic Paths for Lock Conflicts

PGRetry provides two complementary diagnostic channels for analyzing lock contention:

1. **Inferred (default, works everywhere):**
   `detect_blocking_chains(locks)` pairs ungranted lock requests (`granted=False`) against granted locks (`granted=True`) sharing the identical resource key (`lock_type, relation_name, schema_name, page, tuple, transaction_id`). Crucially, relation lock pairs are filtered through PostgreSQL's official 8-mode relation lock compatibility matrix (`_RELATION_LOCK_COMPATIBILITY`, Table 13.2 in PostgreSQL documentation), eliminating false positives between compatible concurrent locks (such as concurrent `AccessShareLock` reads or concurrent `RowExclusiveLock` writes on separate rows). The resulting `BlockingRelationship.authoritative` attribute is set to `False`.

2. **Authoritative:**
   `fetch_locks_with_authoritative(executor)` and `fetch_blocking_pids(executor, pid=...)` query PostgreSQL's built-in `pg_blocking_pids(pid)` function. This queries the server's authoritative kernel lock wait queues, returning `AuthoritativeBlocking(blocked_pid=..., blocking_pids=[...])` structures indicating precisely which backend PIDs are holding back a waiting transaction.

### Diagnostic Privileges

Reading `pg_locks` and `pg_blocking_pids` requires no privileges beyond the ability to see your own backend; reading all backends requires `pg_monitor` or superuser. PGRetry's tests exercise the self-visible path (or the superuser path when running in compose).

### `LockInfo` Dataclass

```python
@dataclass(frozen=True, slots=True)
class LockInfo:
    pid: int
    lock_type: str  # "relation", "transactionid", "tuple", "virtualxid"
    mode: str  # "RowExclusiveLock", "ExclusiveLock", "ShareLock"
    granted: bool  # True if held; False if blocked waiting
    relation_name: Optional[str]  # e.g. "accounts"
    schema_name: Optional[str]  # e.g. "public"
    page: Optional[int]
    tuple: Optional[int]
    transaction_id: Optional[str]
    virtual_transaction: Optional[str]
```

### Blocking Chain Detection (`detect_blocking_chains`)

PGRetry matches ungranted lock requests (`granted=False`) against granted locks (`granted=True`) matching the identical resource key (`lock_type, relation_name, schema_name, page, tuple, transaction_id`).

```python
from pgretry.postgres.locks import detect_blocking_chains

blocking_chains = detect_blocking_chains(locks)
for block in blocking_chains:
    print(f"Process {block.blocked_pid} is BLOCKED by Process {block.blocking_pid}")
    print(f"Waiting for {block.waiting_mode}; Holder has {block.holding_mode}")
    print(f"Resource: {block.resource_description} (authoritative={block.authoritative})")
```

### Authoritative Blocking Inspection (`fetch_locks_with_authoritative`)

```python
from pgretry.postgres.locks import fetch_locks_with_authoritative

locks, authoritative_blocking = await fetch_locks_with_authoritative(executor)
for auth in authoritative_blocking:
    print(f"Blocked PID {auth.blocked_pid} is waiting for PIDs: {auth.blocking_pids}")
```

### Crucial Limitation: SSI (`40001`) vs. Heavyweight Locks (`pg_locks`)

> [!WARNING]
> **Do not expect `pg_locks` to explain every `40001` serialization failure.**
>
> pg_locks cannot fully explain SSI serialization failures (SQLSTATE 40001); SIREAD locks are tracked in-memory and may not appear as ordinary lock waits.
>
> PostgreSQL's Serializable Snapshot Isolation (SSI) engine detects read/write anti-dependencies using **SIREAD predicate locks**. Predicate locks are in-memory tracking flags that do not block execution; transactions proceed normally until commit time, where PostgreSQL aborts any transaction participating in a cycle.
>
> Because predicate locks are not blocking locks, `pg_locks` will generally show **no waiting locks** during a pure SSI serialization failure. PGRetry explicitly identifies this distinction in its diagnostic explanations ("No blocking relationship was found in pg_locks; this is expected for Serializable Snapshot Isolation, where serialization conflicts are tracked via SIREAD predicate locks and may not appear as ordinary lock waits.") and warnings.

---

---

## Diagnostic Reports & Modes

The `DiagnosticCollector` provides four operational modes controlling when diagnostic queries run:

| Mode | Enum Value | Behavior | Recommended Environment |
| :--- | :--- | :--- | :--- |
| `OFF` | `DiagnosticMode.OFF` | Zero queries executed; returns `None`. Zero runtime overhead. | High-throughput production (default) |
| `ON_FAILURE` | `DiagnosticMode.ON_FAILURE` | Queries executed only when a transaction fails. | Staging / Debugging production |
| `SAMPLED` | `DiagnosticMode.SAMPLED` | Executed probabilistically according to `sample_rate` (e.g. 5%). | Production telemetry profiling |
| `ALWAYS` | `DiagnosticMode.ALWAYS` | Executed on every attempt (success or failure). | Test suites & local benchmarking |

### `DiagnosticReport` Structure

```python
@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    transaction_id: Optional[str]
    attempt: int
    sqlstate: Optional[str]
    error_category: PostgresErrorCategory
    error_message: str
    duration: float
    error_detail: Optional[str]
    error_hint: Optional[str]
    isolation_level: Optional[str]
    pid: Optional[int]
    active_sessions: List[SessionActivity]
    locks: List[LockInfo]
    blocking_chains: List[BlockingRelationship]
    explanation: str
    warnings: List[str]
    recommendations: List[str]
```

### Automated Recommendations Engine

PGRetry inspects the error and lock state to generate targeted guidance:

* **For `40001` (Serialization Failure):** Recommends whole-transaction retries with jitter, keeping read-write sets minimal, and declaring read-only transactions as `READ ONLY`.
* **For `40P01` (Deadlock):** Details the exact blocking chain and recommends acquiring locks in consistent global order across application endpoints.
* **For `23505` (Unique Violation):** Flags the error as non-retryable deterministic business logic and advises against automated retries.

---
