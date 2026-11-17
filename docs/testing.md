# Testing Guide & CI Architecture

## Testing

PGRetry features an extensive test suite validating all lifecycle states, retry bounds, mathematical distributions, and integration adapters.

### Running Tests

Run the test suite using Poetry and pytest:

```bash
poetry run pytest
```

### Running integration tests against a real PostgreSQL

```bash
docker compose up -d --wait
export PGRETRY_TEST_DSN="postgresql://postgres:postgres@localhost:5432/postgres"
pytest -m integration
```

The healthcheck in `docker compose` uses `pg_isready` with `--wait` so tests don't race a half-started DB.

#### Continuous integration

CI runs lint (advisory in Phase 5), unit tests without database dependencies, integration tests against a `services: postgres` container, and a compose verification job that runs `docker compose up -d --wait`. If the compose verification job is red, the compose file is broken; if the `services:` job is red, the code is broken. This separation ensures container orchestration defects are diagnosed independently from database driver logic.

### Verified Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.1.1, pluggy-1.6.0
collected 110 items

tests\integration\test_end_to_end.py ........                            [  7%]
tests\integration\test_postgres_concurrency.py ss                        [  9%]
tests\unit\test_asyncpg_integration.py ....                              [ 12%]
tests\unit\test_backoff.py ........                                      [ 20%]
tests\unit\test_classifier.py ..................                         [ 36%]
tests\unit\test_decorator.py .....                                       [ 40%]
tests\unit\test_logging.py ..........                                    [ 50%]
tests\unit\test_metrics.py ..                                            [ 51%]
tests\unit\test_policy.py ........                                       [ 59%]
tests\unit\test_postgres_activity.py ....                                [ 62%]
tests\unit\test_postgres_diagnostics.py .....                            [ 67%]
tests\unit\test_postgres_errors.py .........                             [ 75%]
tests\unit\test_postgres_locks.py .......                                [ 81%]
tests\unit\test_runner_instrumentation.py .....                          [ 86%]
tests\unit\test_sqlalchemy_integration.py .....                          [ 90%]
tests\unit\test_transaction.py ..........                                [100%]

======================= 108 passed, 2 skipped in 3.02s ========================
```

*(Note: The 2 skipped tests in `test_postgres_concurrency.py` dynamically verify whether a live PostgreSQL server is reachable at `localhost:5432`; if not present, they skip gracefully without failing the build).*

---
