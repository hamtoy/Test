# AI Agent Improvement Prompts

## Mandatory Execution Rules
1. Execute prompts strictly in order: PROMPT-001 → PROMPT-007 → OPT-1.
2. Do not respond with text-only explanations. Apply changes via file-edit tools first.
3. Use file-edit tools for every change (replace_string_in_file, multi_replace_string_in_file, create_file).
4. After finishing each prompt: run the verification commands, then update the checklist Status for that prompt.
5. Keep scope tight: implement only what the prompt requests. Do not add historical logs.

## Execution Checklist
| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | Decouple optional Neo4j dependency from base install | P1 | ⬜ Pending |
| 2 | PROMPT-002 | Add CI gate for minimal (no-extras) install | P2 | ⬜ Pending |
| 3 | PROMPT-003 | Unskip Web API tests by mocking LLM calls | P2 | ⬜ Pending |
| 4 | PROMPT-004 | Sync docs with current scripts and commands | P2 | ⬜ Pending |
| 5 | PROMPT-005 | Make CORS origins configurable via env | P2 | ⬜ Pending |
| 6 | PROMPT-006 | Wire OpenTelemetry initialization (optional) | P3 | ⬜ Pending |
| 7 | PROMPT-007 | Add Web endpoint for cache stats summary | P3 | ⬜ Pending |
| 8 | OPT-1 | Stream cache stats analytics (JSONL) | OPT | ⬜ Pending |

Total: 8 prompts | Completed: 0 | Remaining: 8

## P1 Prompts

### [PROMPT-001] Decouple optional Neo4j dependency from base install
Execute this prompt now, then proceed to [PROMPT-002].

**Task**
Ensure `import src.main` and `import src.cli` work when the `neo4j` package is not installed, while keeping Neo4j optimization functionality available when explicitly enabled.

**Target Files**
- `src/cli.py`
- `src/infra/neo4j_optimizer.py`
- `tests/integration/test_main_execution.py` (or a new integration test file)

**Steps**
1. In `src/cli.py`, remove any top-level imports that require optional packages (notably `neo4j` and any Neo4j-only helpers).
2. Add a lazy import helper (example structure):
   - `def _load_two_tier_index_manager() -> type[object]: ...`
   - Perform the imports inside the function.
   - On `ImportError`, raise a clear `RuntimeError` explaining which extra/dependency to install to enable the Neo4j optimization path.
3. Ensure the Neo4j optimization code path is only executed when the related CLI flag is used (for example `--optimize-neo4j`), and that the rest of the CLI remains fully usable without Neo4j installed.
4. Add an integration test that runs a subprocess and simulates the `neo4j` module being unavailable (for example by setting `sys.modules["neo4j"] = None` inside the subprocess), then imports `src.main` and asserts import success.

**Implementation Notes**
- Do not change public CLI argument names or defaults.
- Keep error messages consistent with existing style (raise exceptions; do not print in library code).
- The Neo4j optimization feature should fail fast with a helpful error if invoked without the dependency installed.

**Verification**
- `uv sync --extra dev`
- `uv run python -c "import src; import src.main; import src.cli; print('OK')"`
- `uv run pytest -q tests/integration/test_main_execution.py`

After completing this prompt, proceed to [PROMPT-002].

## P2 Prompts (Part 1)

### [PROMPT-002] Add CI gate for minimal (no-extras) install
Execute this prompt now, then proceed to [PROMPT-003].

**Task**
Add a CI job that installs only the base dependencies (no optional extras) and verifies core imports succeed. This should catch optional-dependency coupling regressions early.

**Target Files**
- `.github/workflows/ci.yaml`

**Steps**
1. Add a new job (for example `minimal-install`) that runs on Linux with a single Python version (suggested: 3.12).
2. Use the same toolchain as the existing CI (setup Python + setup uv).
3. Install base dependencies only (for example `uv sync` without `--extra dev`).
4. Run a short import smoke check that should succeed under base install:
   - `uv run python -c "import src; import src.main; import src.cli; print('MINIMAL_OK')"`
5. Ensure this job does not require services (Neo4j/Redis) and runs quickly.

**Verification**
- Validate the workflow YAML locally (syntax) and ensure it is consistent with the current CI style.

After completing this prompt, proceed to [PROMPT-003].

### [PROMPT-003] Unskip Web API tests by mocking LLM calls
Execute this prompt now, then proceed to [PROMPT-004].

**Task**
Remove skip markers in `tests/test_web_api.py` that exist due to external LLM/API requirements, and make the tests deterministic by using mocks/fixtures.

**Target Files**
- `tests/test_web_api.py`
- `tests/conftest.py`
- `src/llm/gemini.py` (only if strictly needed to improve testability)

**Steps**
1. In `tests/test_web_api.py`, remove `@pytest.mark.skip(...)` decorators for endpoints that can be tested with mocks.
2. Ensure the module uses the existing `mock_genai` fixture so that no real network calls occur. Prefer one of:
   - Update the `client` fixture to depend on `mock_genai`, or
   - Add `pytestmark = pytest.mark.usefixtures("mock_genai")` at module level.
3. Adjust the mock objects in `tests/conftest.py` so that the object returned by `google.generativeai.GenerativeModel(...)` has a `generate_content(...)` method returning a response with a `.text` value that satisfies the current endpoint expectations in `tests/test_web_api.py`.
4. For optional multimodal endpoints, make tests conditional on the dependency being available or mock the multimodal implementation so the endpoints can be exercised without optional extras.

**Verification**
- `uv sync --extra dev`
- `uv run pytest -q tests/test_web_api.py`

After completing this prompt, proceed to [PROMPT-004].

## P2 Prompts (Part 2)

### [PROMPT-004] Sync docs with current scripts and commands
Execute this prompt now, then proceed to [PROMPT-005].

**Task**
Update documentation so it does not reference scripts/commands that no longer exist in the repository, and ensure the documented commands match the current tooling.

**Target Files**
- `README.md`
- `docs/README_FULL.md`
- `docs/CACHING.md`
- `docs/ADVANCED_FEATURES.md`
- `docs/MONITORING.md`
- `docs/IMPROVEMENT_PROPOSAL.md`

**Steps**
1. Search for references to removed scripts (at minimum):
   - `scripts/auto_profile.py`
   - `scripts/compare_runs.py`
   - `scripts/cache_warming.py`
2. For each reference:
   - Replace with the current equivalent script/command if one exists, or
   - Remove the instruction and add a short note that the capability is not currently provided by a script.
3. Ensure examples use commands that exist in the repo today (check `scripts/` directory and `pyproject.toml` scripts).
4. Keep the docs internally consistent (avoid conflicting installation/run instructions across files).

**Verification**
- `rg -n \"auto_profile\\.py|compare_runs\\.py|cache_warming\\.py\" README.md docs || true`
- `ls -la scripts`

After completing this prompt, proceed to [PROMPT-005].

### [PROMPT-005] Make CORS origins configurable via env
Execute this prompt now, then proceed to [PROMPT-006].

**Task**
Replace hard-coded CORS origins in the FastAPI app with an environment-configurable setting, while keeping the current local defaults.

**Target Files**
- `src/web/api.py`
- `src/config/settings.py`
- `tests/unit/config/test_config_validation.py`
- `docs/MONITORING.md` (or another appropriate ops doc)

**Steps**
1. In `src/config/settings.py`, add a new `AppConfig` field for CORS origins, sourced from an env var such as `CORS_ALLOW_ORIGINS`.
2. Implement robust parsing:
   - Accept comma-separated strings (trim whitespace; ignore empty entries).
   - Preserve a sensible default list equivalent to the current hard-coded local origins.
3. In `src/web/api.py`, replace the current `allow_origins=[...]` with the config-driven value.
4. Add/extend unit tests in `tests/unit/config/test_config_validation.py` to cover:
   - Default behavior (no env var set).
   - Custom env var value with multiple entries and whitespace.
   - Empty/invalid env var handling (should fall back safely).
5. Update documentation with a short example of how to set `CORS_ALLOW_ORIGINS` for local and production use.

**Implementation Notes**
- Keep the default behavior unchanged for local development.
- Do not loosen CORS beyond what is configured; avoid `*` defaults.

**Verification**
- `uv sync --extra dev`
- `uv run pytest -q tests/unit/config/test_config_validation.py`
- `uv run pytest -q tests/test_web_api.py`

After completing this prompt, proceed to [PROMPT-006].

## P3 Prompts

### [PROMPT-006] Wire OpenTelemetry initialization (optional)
Execute this prompt now, then proceed to [PROMPT-007].

**Task**
Enable OpenTelemetry initialization at runtime when an OTLP endpoint is configured, without adding a hard dependency on OpenTelemetry packages.

**Target Files**
- `src/infra/telemetry.py`
- `src/web/api.py`
- `src/infra/worker.py`
- `docs/MONITORING.md` (or an ops doc of your choice)

**Steps**
1. Keep `src/infra/telemetry.init_telemetry(...)` as the single entry point. It must remain safe when OpenTelemetry is not installed.
2. In `src/web/api.py`, call `init_telemetry(service_name=...)` during application startup (for example inside `lifespan(...)` before handling requests).
3. In `src/infra/worker.py`, call `init_telemetry(service_name=...)` before the worker starts processing tasks.
4. Document the required env var (`OTEL_EXPORTER_OTLP_ENDPOINT`) and a minimal example configuration.

**Implementation Notes**
- Do not fail startup if telemetry is unavailable; log and continue.
- Avoid repeated initialization on reload paths (keep it idempotent or guarded).

**Verification**
- `uv sync --extra dev`
- `uv run python -c "from src.infra.telemetry import init_telemetry; init_telemetry(); print('OTEL_OK')"`
- `uv run pytest -q tests/test_health.py`

After completing this prompt, proceed to [PROMPT-007].

### [PROMPT-007] Add Web endpoint for cache stats summary
Execute this prompt now, then proceed to [OPT-1].

**Task**
Expose a read-only Web API endpoint that returns a JSON summary of cache statistics from the configured cache stats JSONL file.

**Target Files**
- `src/caching/analytics.py`
- `src/web/api.py`
- `src/web/routers/__init__.py`
- `src/web/routers/` (add a new router module, for example `cache_stats.py`)
- `tests/test_web_api.py`

**Steps**
1. Create a new FastAPI router under `src/web/routers/`:
   - Define `router = APIRouter(...)` with a prefix like `/api/cache`.
   - Add `GET /summary` that returns the output of `analyze_cache_stats(...)`.
2. Follow the existing dependency-injection pattern used by other routers:
   - Implement `set_dependencies(config: AppConfig, ...)` if needed.
   - Use `config.cache_stats_path` as the default file location.
3. Handle errors explicitly:
   - If the stats file is missing, return HTTP 404.
   - If JSONL lines are malformed, skip them (do not fail the endpoint).
4. Register the router in `src/web/api.py` so it is included in the app.
5. Add tests in `tests/test_web_api.py`:
   - Create a temp JSONL stats file with at least one valid line and one invalid line.
   - Inject a config pointing to that file using the router dependency setter.
   - Assert the endpoint returns 200 and the expected response keys.

**Verification**
- `uv sync --extra dev`
- `uv run pytest -q tests/test_web_api.py`

After completing this prompt, proceed to [OPT-1].

## Optimization Prompts (OPT)

### [OPT-1] Stream cache stats analytics (JSONL)
Execute this prompt now, then proceed to the Final Completion section.

**Task**
Refactor cache stats analytics to process JSONL input in a streaming manner (constant memory), while keeping the output schema stable.

**Target Files**
- `src/caching/analytics.py`
- `tests/test_caching_analytics.py` (add coverage for `analyze_cache_stats`)

**Steps**
1. Refactor `analyze_cache_stats(path: Path) -> dict[str, Any]`:
   - Do not store all records in a list.
   - Maintain running counters for records, hits, misses, and estimated savings.
   - Skip empty lines and malformed JSON lines safely.
2. Keep the returned keys stable:
   - `total_records`, `total_hits`, `total_misses`, `hit_rate`, `estimated_savings_usd`
3. Add tests that validate:
   - Correct aggregation on a small JSONL file.
   - Malformed lines are ignored (no exception, counts unaffected).
   - Output values match expected numbers.

**Verification**
- `uv sync --extra dev`
- `uv run pytest -q tests/test_caching_analytics.py`

After completing this prompt, proceed to the Final Completion section.

## Final Completion
1. Confirm every prompt in the checklist is marked as completed.
2. Run final verification:
   - `uv sync --extra dev`
   - `uv run ruff check .`
   - `uv run mypy .`
   - `uv run pytest -q`
3. Print exactly:
   - `ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.`
