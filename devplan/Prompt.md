# AI Agent Improvement Prompts

## 1. Execution Rules (Mandatory)

1. **No Text-Only Responses:** Do not output long explanations. Use file-edit tools immediately.
2. **Sequential Execution:** Follow the checklist order strictly. Do not skip prompts.
3. **Use File Tools:** All code changes must be applied using `write_to_file`, `replace_file_content`, or `run_command`.
4. **Verification:** Run the specified verification commands after each prompt.
5. **Complete Implementation:** Provide actual implementation code, not placeholders like `// TODO` or `// ...`.

---

## 2. Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | **PROMPT-001** | API Documentation Automation | P2 | ✅ Done (docs.yml) |
| 2 | **PROMPT-002** | Monitoring Alerting Configuration | P2 | ✅ Done |
| 3 | **PROMPT-003** | Security Scanning CI Integration | P3 | ✅ Done (security.yml) |
| 4 | **PROMPT-004** | External Dependency Mocking | P3 | ✅ Done |
| 5 | **OPT-1** | CLI Help Enhancement | OPT | ✅ Done (already implemented) |
| 6 | **OPT-2** | Caching Layer Visibility | OPT | ✅ Done (metrics.py) |

**Total: 6 prompts | Completed: 6 | Remaining: 0**

---

## 3. Improvement Prompts (P2)

### [PROMPT-001] API Documentation Automation

**Directive:** Execute this prompt now, then proceed to PROMPT-002.

**Task:**
Create a script that converts the FastAPI OpenAPI specification to Markdown documentation and generates versioned API reference files.

**Target Files:**

- `scripts/generate_api_docs.py` (NEW)
- `docs/api/v3.0.0.md` (NEW)

**Steps:**

1. Create `scripts/generate_api_docs.py`:
   - Import FastAPI app from `src.web.server`
   - Extract OpenAPI schema using `app.openapi()`
   - Convert paths, schemas, and examples to Markdown format
   - Write output to `docs/api/` directory

2. Create the documentation file with these sections:
   - API Overview (base URL, authentication)
   - Endpoints grouped by tag
   - Request/Response schemas with examples
   - Error codes and descriptions

3. Update `README.md` to add link to API documentation.

**Implementation Code:**

```python
#!/usr/bin/env python3
"""Generate API documentation from OpenAPI spec."""

import json
from pathlib import Path


def generate_markdown(openapi_spec: dict) -> str:
    """Convert OpenAPI spec to Markdown documentation."""
    md_lines = [
        f"# {openapi_spec.get('info', {}).get('title', 'API')} Documentation",
        "",
        f"Version: {openapi_spec.get('info', {}).get('version', '1.0.0')}",
        "",
        openapi_spec.get("info", {}).get("description", ""),
        "",
        "## Endpoints",
        "",
    ]

    paths = openapi_spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                summary = details.get("summary", path)
                md_lines.append(f"### `{method.upper()}` {path}")
                md_lines.append("")
                md_lines.append(f"**Summary:** {summary}")
                md_lines.append("")
                if "description" in details:
                    md_lines.append(details["description"])
                    md_lines.append("")

    return "\n".join(md_lines)


def main() -> None:
    """Main entry point."""
    try:
        from src.web.server import create_app

        app = create_app()
        openapi_spec = app.openapi()
    except ImportError:
        # Fallback: read from saved spec
        spec_path = Path("docs/openapi.json")
        if spec_path.exists():
            openapi_spec = json.loads(spec_path.read_text())
        else:
            print("Could not load OpenAPI spec")
            return

    output_dir = Path("docs/api")
    output_dir.mkdir(parents=True, exist_ok=True)

    version = openapi_spec.get("info", {}).get("version", "1.0.0")
    output_file = output_dir / f"v{version}.md"

    markdown = generate_markdown(openapi_spec)
    output_file.write_text(markdown, encoding="utf-8")
    print(f"Generated: {output_file}")


if __name__ == "__main__":
    main()
```

**Verification:**

```bash
# Run the script
uv run python scripts/generate_api_docs.py

# Check file creation
ls -l docs/api/
```

After completing this prompt, proceed to **PROMPT-002**.

---

### [PROMPT-002] Monitoring Alerting Configuration

**Directive:** Execute this prompt now, then proceed to PROMPT-003.

**Task:**
Configure Grafana alerting rules to notify when error rates or latency exceed thresholds.

**Target Files:**

- `grafana/provisioning/alerting/rules.yaml` (NEW)
- `grafana/provisioning/alerting/contact_points.yaml` (NEW)

**Steps:**

1. Create the alerting directory structure:

   ```
   grafana/provisioning/alerting/
   ```

2. Create `rules.yaml` with alert rules for:
   - Error rate > 5% over 5 minutes
   - Average latency > 5 seconds
   - System memory usage > 90%

3. Create `contact_points.yaml` with placeholder notification configuration.

**Implementation Code:**

```yaml
# grafana/provisioning/alerting/rules.yaml
apiVersion: 1

groups:
  - orgId: 1
    name: shining-quasar-alerts
    folder: Alerting
    interval: 1m
    rules:
      - uid: error-rate-alert
        title: High Error Rate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
              instant: false
              intervalMs: 1000
              maxDataPoints: 43200
              refId: A
          - refId: C
            datasourceUid: __expr__
            model:
              conditions:
                - evaluator:
                    params:
                      - 0.05
                    type: gt
                  operator:
                    type: and
                  query:
                    params:
                      - A
                  reducer:
                    type: avg
              refId: C
              type: classic_conditions
        noDataState: NoData
        execErrState: Error
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Error rate is above 5%
          description: The error rate has exceeded 5% over the last 5 minutes.

      - uid: high-latency-alert
        title: High Latency
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
          - refId: C
            datasourceUid: __expr__
            model:
              conditions:
                - evaluator:
                    params:
                      - 5
                    type: gt
        noDataState: NoData
        execErrState: Error
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: API latency is high
          description: 95th percentile latency exceeds 5 seconds.
```

```yaml
# grafana/provisioning/alerting/contact_points.yaml
apiVersion: 1

contactPoints:
  - orgId: 1
    name: default-email
    receivers:
      - uid: email-receiver
        type: email
        settings:
          addresses: admin@example.com
        disableResolveMessage: false
```

**Verification:**

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('grafana/provisioning/alerting/rules.yaml'))"

# Check file structure
ls -la grafana/provisioning/alerting/
```

After completing this prompt, proceed to **PROMPT-003**.

---

## 4. Improvement Prompts (P3)

### [PROMPT-003] Security Scanning CI Integration

**Directive:** Execute this prompt now, then proceed to PROMPT-004.

**Task:**
Add a GitHub Actions workflow that runs Bandit static analysis and Safety dependency checks on every pull request.

**Target Files:**

- `.github/workflows/security.yml` (NEW)

**Steps:**

1. Create the security workflow file.
2. Configure Bandit to scan Python source code.
3. Configure Safety to check for known vulnerabilities in dependencies.
4. Set up failure conditions for critical findings.

**Implementation Code:**

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  bandit:
    name: Bandit Static Analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Bandit
        run: pip install bandit[toml]

      - name: Run Bandit
        run: |
          bandit -r src/ -c pyproject.toml -f json -o bandit-report.json || true
          bandit -r src/ -c pyproject.toml -ll

      - name: Upload Bandit Report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bandit-report
          path: bandit-report.json

  safety:
    name: Dependency Vulnerability Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --dev

      - name: Run Safety Check
        run: |
          uv pip install safety
          safety check --full-report || echo "Vulnerabilities found"
        continue-on-error: true
```

**Verification:**

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/security.yml'))"

# Check workflow file exists
ls -l .github/workflows/security.yml
```

After completing this prompt, proceed to **PROMPT-004**.

---

### [PROMPT-004] External Dependency Mocking

**Directive:** Execute this prompt now, then proceed to OPT-1.

**Task:**
Create pytest fixtures for mocking Neo4j and Redis connections to improve test isolation and CI reliability.

**Target Files:**

- `tests/fixtures/mock_neo4j.py` (NEW)
- `tests/fixtures/mock_redis.py` (NEW)
- `tests/fixtures/__init__.py` (NEW)
- `tests/conftest.py` (UPDATE)

**Steps:**

1. Create the fixtures directory structure.
2. Implement mock Neo4j driver fixture.
3. Implement mock Redis client fixture.
4. Register fixtures in conftest.py.

**Implementation Code:**

```python
# tests/fixtures/__init__.py
"""Test fixtures package for external dependency mocking."""

from tests.fixtures.mock_neo4j import mock_neo4j_driver
from tests.fixtures.mock_redis import mock_redis_client

__all__ = ["mock_neo4j_driver", "mock_redis_client"]
```

```python
# tests/fixtures/mock_neo4j.py
"""Mock Neo4j driver for testing."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


class MockNeo4jSession:
    """Mock Neo4j session."""

    def __init__(self) -> None:
        self.run = MagicMock(return_value=MagicMock(data=lambda: []))
        self.close = MagicMock()

    def __enter__(self) -> "MockNeo4jSession":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class MockNeo4jDriver:
    """Mock Neo4j driver."""

    def __init__(self) -> None:
        self._closed = False

    def session(self, **kwargs: Any) -> MockNeo4jSession:
        return MockNeo4jSession()

    def close(self) -> None:
        self._closed = True

    def verify_connectivity(self) -> None:
        pass


@pytest.fixture
def mock_neo4j_driver() -> Generator[MockNeo4jDriver, None, None]:
    """Provide a mock Neo4j driver for testing."""
    driver = MockNeo4jDriver()
    yield driver
    driver.close()
```

```python
# tests/fixtures/mock_redis.py
"""Mock Redis client for testing."""

from typing import Any, Generator
from unittest.mock import AsyncMock

import pytest


class MockRedisClient:
    """Mock async Redis client."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.get = AsyncMock(side_effect=self._get)
        self.set = AsyncMock(side_effect=self._set)
        self.delete = AsyncMock(side_effect=self._delete)
        self.exists = AsyncMock(side_effect=self._exists)
        self.close = AsyncMock()

    async def _get(self, key: str) -> Any:
        return self._data.get(key)

    async def _set(self, key: str, value: Any, **kwargs: Any) -> bool:
        self._data[key] = value
        return True

    async def _delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def _exists(self, key: str) -> int:
        return 1 if key in self._data else 0


@pytest.fixture
def mock_redis_client() -> Generator[MockRedisClient, None, None]:
    """Provide a mock Redis client for testing."""
    client = MockRedisClient()
    yield client
```

**Update conftest.py** by adding at the top:

```python
# Add to tests/conftest.py
pytest_plugins = ["tests.fixtures"]
```

**Verification:**

```bash
# Run tests with the new fixtures
uv run pytest tests/fixtures/ -v

# Run a simple test to verify fixtures work
uv run pytest tests/ -k "mock" -v --tb=short
```

After completing this prompt, proceed to **OPT-1**.

---

## 5. Optimization Prompts (OPT)

### [OPT-1] CLI Help Enhancement

**Directive:** Execute this prompt now, then proceed to OPT-2.

**Task:**
Enhance the CLI help output using Rich library for better readability and add usage examples.

**Target Files:**

- `src/cli.py` (UPDATE)

**Steps:**

1. Create a custom help formatter using Rich.
2. Add examples to each command.
3. Group commands by category.

**Implementation Code:**

Add the following function to `src/cli.py`:

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def print_rich_help() -> None:
    """Print enhanced help using Rich library."""
    console = Console()

    console.print(Panel.fit(
        "[bold blue]shining-quasar[/bold blue] - Graph RAG QA System",
        subtitle="v3.0.0"
    ))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Command", style="green")
    table.add_column("Description")
    table.add_column("Example", style="dim")

    table.add_row(
        "run",
        "Start the web server",
        "uv run python -m src.cli run --port 8000"
    )
    table.add_row(
        "query",
        "Execute a single query",
        "uv run python -m src.cli query 'What is X?'"
    )
    table.add_row(
        "health",
        "Check system health",
        "uv run python -m src.cli health"
    )

    console.print(table)
    console.print("\n[dim]Use --help with any command for more details.[/dim]")
```

**Verification:**

```bash
# Run CLI with help flag
uv run python -m src.cli --help

# Check syntax
uv run python -m mypy src/cli.py
```

After completing this prompt, proceed to **OPT-2**.

---

### [OPT-2] Caching Layer Visibility

**Directive:** Execute this prompt now, then proceed to Final Verification.

**Task:**
Add Prometheus metrics for cache hit/miss rates to improve observability.

**Target Files:**

- `src/monitoring/metrics.py` (UPDATE)
- `src/caching/cache_manager.py` (UPDATE - if exists)

**Steps:**

1. Add cache metrics to the monitoring module.
2. Instrument cache operations to record hits and misses.

**Implementation Code:**

Add to `src/monitoring/metrics.py`:

```python
from prometheus_client import Counter

# Cache metrics
CACHE_HIT_TOTAL = Counter(
    "cache_hit_total",
    "Total number of cache hits",
    ["cache_name"]
)

CACHE_MISS_TOTAL = Counter(
    "cache_miss_total",
    "Total number of cache misses",
    ["cache_name"]
)


def record_cache_hit(cache_name: str = "default") -> None:
    """Record a cache hit event."""
    CACHE_HIT_TOTAL.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str = "default") -> None:
    """Record a cache miss event."""
    CACHE_MISS_TOTAL.labels(cache_name=cache_name).inc()
```

**Verification:**

```bash
# Check syntax
uv run python -m mypy src/monitoring/metrics.py

# Run related tests
uv run pytest tests/unit/monitoring/ -v
```

After completing this prompt, proceed to **Final Verification**.

---

## 6. Final Steps

**Directive:** Run the final verification.

**Actions:**

1. Check that all new files were created:
   - `scripts/generate_api_docs.py`
   - `grafana/provisioning/alerting/rules.yaml`
   - `grafana/provisioning/alerting/contact_points.yaml`
   - `.github/workflows/security.yml`
   - `tests/fixtures/mock_neo4j.py`
   - `tests/fixtures/mock_redis.py`

2. Run the test suite to ensure no regressions:

   ```bash
   uv run pytest tests/ -x --tb=short
   ```

3. Run type checking:

   ```bash
   uv run python -m mypy src/
   ```

4. Print the following completion message:

```text
ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.

Summary:
- PROMPT-001: API Documentation Automation ✅
- PROMPT-002: Monitoring Alerting Configuration ✅
- PROMPT-003: Security Scanning CI Integration ✅
- PROMPT-004: External Dependency Mocking ✅
- OPT-1: CLI Help Enhancement ✅
- OPT-2: Caching Layer Visibility ✅
```
