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

#### Continuous Integration

CI runs blocking linting (`ruff check .`), strict type checking (`mypy src/pgretry`), unit tests in parallel across Python 3.11, 3.12, and 3.13 without database dependencies, integration tests against a native PostgreSQL 16 service container, and Docker Compose verification. If the compose verification job is red, the compose file is broken; if the `services:` job is red, the code is broken. This separation ensures container orchestration defects are diagnosed independently from database driver logic.

---
