# Retry Policy & Jitter

## RetryPolicy Configuration

The `RetryPolicy` class is a frozen, immutable configuration dataclass governing retry attempts, backoff timing, and target SQLSTATE codes.

```python
from pgretry.retry import RetryPolicy

policy = RetryPolicy(
    max_attempts=5,  # Maximum execution attempts (initial + 4 retries)
    base_delay=0.05,  # Initial backoff delay in seconds (50ms)
    max_delay=2.0,  # Maximum backoff ceiling cap in seconds (2s)
    backoff_factor=2.0,  # Exponential multiplier
    jitter=True,  # Enable randomized Full Jitter
    retryable_sqlstates={"40001", "40P01"},  # Target SQLSTATE codes
)
```

### Configuration Options & Validation Rules

| Attribute | Type | Default | Validation Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `max_attempts` | `int` | `5` | Must be an integer `>= 1` | Total execution attempts permitted before permanently raising the final failure. |
| `base_delay` | `float` | `0.05` | Must be `>= 0.0` | Initial delay base (in seconds) applied before the first retry attempt. |
| `max_delay` | `float` | `2.0` | Must be `>= base_delay` | Maximum delay cap (in seconds) for any backoff interval. |
| `backoff_factor`| `float` | `2.0` | Must be `>= 1.0` | Multiplier for exponential delay scaling (`base_delay * (factor ** attempt)`). |
| `jitter` | `bool` | `True` | Boolean | When `True`, applies randomized Full Jitter between `0.0` and the calculated ceiling. |
| `retryable_sqlstates`| `FrozenSet[str]` | `{"40001", "40P01"}` | Normalized to uppercase | Set of 5-character SQLSTATE codes that trigger retries. |

Instances of `RetryPolicy` are strictly immutable (`frozen=True, slots=True`). Any attempt to modify fields post-initialization raises `dataclasses.FrozenInstanceError`.

---

---

## Exponential Backoff with Full Jitter

When a database experiences high concurrency contention, multiple transactions often fail almost simultaneously. If those transactions immediately retry, or retry on identical fixed timers, they collide again—a phenomenon known as the **thundering herd** problem.

PGRetry implements **Full Jitter** exponential backoff (as documented in AWS architecture research):

$$\text{ceiling} = \min(\text{max\_delay}, \text{base\_delay} \times (\text{backoff\_factor}^{\text{attempt}}))$$
$$\text{delay} = \text{random.uniform}(0.0, \text{ceiling}) \quad \text{(if jitter is enabled)}$$

### Without Jitter vs. With Jitter Progression

Suppose three concurrent transactions encounter a serialization conflict at $T = 0$:

```text
WITHOUT JITTER (backoff_factor=2.0, base_delay=0.1s):
All clients calculate identical fixed intervals and collide again:
Client A: ──── 100ms ────► Retry (Collides with B & C!)
Client B: ──── 100ms ────► Retry (Collides with A & C!)
Client C: ──── 100ms ────► Retry (Collides with A & B!)

WITH FULL JITTER (PGRetry default):
Delays are uniformly distributed across [0.0, ceiling]:
Client A: ── 42ms ──► Retry (Succeeds)
Client B: ──── 87ms ────► Retry (Succeeds)
Client C: ────── 115ms ──────► Retry (Succeeds)
```

The backoff calculator is mathematically bounded: delay is guaranteed to be non-negative (`>= 0.0`), never exceeds `max_delay`, and guards against Python float exponent overflow on large attempt numbers.

---
