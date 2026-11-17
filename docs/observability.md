# Observability, Logging & Telemetry

## Structured Logging & Credential Redaction

The `TransactionLogger` produces structured, machine-readable logs compatible with Datadog, ELK, Grafana Loki, and CloudWatch.

### Standard Logger Configuration

By default, logs are emitted under the logger hierarchy `pgretry.transaction`:

```python
import logging
from pgretry.instrumentation import TransactionLogger

# Attach standard Python logging handler
logging.basicConfig(level=logging.INFO)

# Initialize logger
tx_logger = TransactionLogger(enabled=True)
```

### Emitted Lifecycle Events

| Event Type | Log Level | Emitted When |
| :--- | :--- | :--- |
| `transaction_started` | `DEBUG` | A new attempt begins execution. |
| `transaction_committed` | `INFO` | An attempt completes and successfully commits. |
| `transaction_rolled_back` | `WARNING` | An exception occurs and rollback is issued. |
| `transaction_retry` | `WARNING` | A retryable error triggers backoff delay and subsequent replay. |
| `transaction_failed` | `ERROR` | A transaction fails permanently (non-retryable or attempts exhausted). |

### Automatic Credential and URL Redaction

PGRetry includes recursive sanitization (`sanitize_value`) that executes automatically across all event metadata:

1. **Sensitive Key Redaction:** Any dictionary key matching passwords, tokens, API keys, credentials, or secrets is replaced with `"[REDACTED]"`.
2. **Database DSN Masking:** Connection URLs (e.g. `postgresql://user:secret123@host:5432/db`) are automatically parsed and masked (`postgresql://user:[REDACTED]@host:5432/db`).

Sample JSON log output (`event.to_dict()`):

```json
{
  "event": "transaction_retry",
  "attempt": 1,
  "duration_ms": 42.15,
  "transaction_id": "order-create-9842",
  "sqlstate": "40001",
  "error_category": "serialization_failure",
  "retry_delay_ms": 78.40,
  "error_message": "could not serialize access due to read/write dependencies",
  "metadata": {
    "user_id": 104,
    "api_key": "[REDACTED]"
  }
}
```

---

---

## Telemetry & Telemetry Metrics

PGRetry provides a decoupled metrics protocol (`MetricsCollector`) and a thread-safe, in-memory implementation (`InMemoryMetricsCollector`) that requires zero third-party monitoring dependencies.

### The `MetricsCollector` Protocol

Any monitoring collector (StatsD, Prometheus client, OpenTelemetry SDK) can implement the protocol:

```python
class MetricsCollector(Protocol):
    def record_transaction_started(self, transaction_id: Optional[str] = None) -> None: ...
    def record_transaction_committed(
        self, duration: float, attempts: int, transaction_id: Optional[str] = None
    ) -> None: ...
    def record_transaction_failed(
        self,
        duration: float,
        attempts: int,
        sqlstate: Optional[str] = None,
        error_category: Optional[str] = None,
    ) -> None: ...
    def record_transaction_retry(
        self,
        attempt: int,
        delay: float,
        sqlstate: Optional[str] = None,
        error_category: Optional[str] = None,
    ) -> None: ...
    def record_serialization_failure(self) -> None: ...
    def record_deadlock(self) -> None: ...
```

### Using `InMemoryMetricsCollector`

```python
from pgretry.instrumentation import InMemoryMetricsCollector

metrics = InMemoryMetricsCollector()

# Pass to runner
runner = TransactionRunner(metrics=metrics)

# Inspect snapshot after traffic
snapshot = metrics.snapshot()
print(f"Total Transactions:      {snapshot.transactions_total}")
print(f"Committed:               {snapshot.transactions_committed_total}")
print(f"Failed:                  {snapshot.transactions_failed_total}")
print(f"Retried:                 {snapshot.transactions_retried_total}")
print(f"Serialization Conflicts: {snapshot.serialization_failures_total}")
print(f"Deadlocks Detected:      {snapshot.deadlocks_total}")
print(f"Average Duration:        {snapshot.avg_duration_seconds * 1000:.2f}ms")
print(f"Average Retry Delay:     {snapshot.avg_retry_delay_seconds * 1000:.2f}ms")
```

---

---

## Transaction Context & Attempt History

During execution, metadata about the active transaction is accessible via Python's standard `contextvars` mechanism.

### Accessing Context Inside Business Logic

You can inspect the live transaction context using `get_current_context()`:

```python
from pgretry.transaction import get_current_context


async def my_operation():
    ctx = get_current_context()
    if ctx is not None:
        print(f"Attempt: {ctx.attempt} of {ctx.max_attempts}")
        print(f"Is Retry: {ctx.is_retry}")
        print(f"Retry Count: {ctx.retry_count}")
        print(f"Total Elapsed Time: {ctx.total_elapsed_time:.3f}s")
        if ctx.last_error:
            print(f"Previous attempt failed with: {ctx.last_error}")
```

### `AttemptRecord`

Every attempt (successful or failed) appends an immutable `AttemptRecord` to `ctx.history`:

* `attempt_number`: 1-based attempt index.
* `start_time`: Monotonic start timestamp in seconds.
* `duration`: Execution time of the attempt in seconds.
* `error`: Exception raised, if any.
* `classification`: The `ClassificationResult` object.
* `backoff_delay`: Delay applied after this attempt (0.0 if not retried).
* `is_success`: `True` if no error occurred.
* `was_retried`: `True` if backoff delay was scheduled for retry.

---
