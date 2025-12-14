# AI Agent Improvement Prompts

## 1. Execution Rules (Mandatory)

1. **No Text-Only Responses:** Do not output long explanations. Use file-edit tools immediately.
2. **Sequential Execution:** Follow the checklist order strictly. Do not skip prompts.
3. **Use File Tools:** All code changes must be applied using `write_to_file`, `replace_file_content`, or `run_command`.
4. **Verification:** Run the specified verification commands after each prompt.

## 2. Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | **PROMPT-001** | Implement Telemetry Dashboard | P2 | ✅ Completed |
| 2 | **PROMPT-002** | Create User Documentation | P3 | ✅ Completed |
| 3 | **OPT-1** | Optimize Neo4j Queries | OPT | ✅ Completed |

**Total: 3 prompts | Completed: 3 | Remaining: 0**

---

## 3. Improvement Prompts (P2)

### [PROMPT-001] Implement Telemetry Dashboard

**Directive:** Execute this prompt now, then proceed to PROMPT-002.

**Task:**
Create a telemetry setup to monitor system metrics, using a new Docker Compose service for Prometheus/Grafana and updating the application to expose metrics.

**Target Files:**

- `docker-compose.monitoring.yml` (NEW)
- `src/monitoring/metrics.py` (UPDATE)
- `src/monitoring/exporter.py` (NEW)
- `src/config/settings.py` (UPDATE)

**Steps:**

1. Create `docker-compose.monitoring.yml` defining `prometheus` and `grafana` services.
2. Create `src/monitoring/exporter.py` to expose a `/metrics` endpoint (if not already handled by FastAPI middleware).
3. Update `src/config/settings.py` to add `ENABLE_METRICS` boolean flag (default: `True`).
4. Ensure `src/monitoring/metrics.py` defines `REQUEST_COUNT`, `REQUEST_LATENCY` (Histogram), and `SYSTEM_CPU_USAGE` (Gauge).

**Verification:**

```bash
# Verify syntax
uv run python -m mypy src/monitoring
# (Optional) Check if docker-compose file is valid
docker-compose -f docker-compose.monitoring.yml config
```

---

## 4. Improvement Prompts (P3)

### [PROMPT-002] Create User Documentation

**Directive:** Execute this prompt now, then proceed to OPT-1.

**Task:**
Create a comprehensive `user_manual.md` to guide end-users on how to install, configure, and use the system.

**Target Files:**

- `docs/user_manual.md` (NEW)
- `README.md` (UPDATE)

**Steps:**

1. Create `docs/user_manual.md`.
2. Document the "Installation" process (Prerequisites, Docker setup).
3. Document "Configuration" (Environment variables in `.env`).
4. Document "Basic Usage" (How to run queries via API or CLI).
5. Add a "Troubleshooting" section for common errors (e.g., 429 Rate Limit, Neo4j connection failure).
6. Update `README.md` to link to the new user manual.

**Verification:**

```bash
# Verify the file creation
ls -l docs/user_manual.md
```

---

## 5. Optimization Prompts (OPT)

### [OPT-1] Optimize Neo4j Queries

**Directive:** Execute this prompt now, then proceed to Final Verification.

**Task:**
Analyze and optimize Cypher query generation to improve Graph RAG retrieval performance, specifically focusing on index usage.

**Target Files:**

- `src/graph/query_builder.py` (UPDATE)
- `scripts/setup_indexes.cypher` (NEW)

**Steps:**

1. Create `scripts/setup_indexes.cypher` containing commands to create indexes for frequently queried node labels and properties (e.g., `CREATE INDEX FOR (n:Entity) ON (n.name);`).
2. Update `src/graph/query_builder.py` to optionally include `USING INDEX` hints if heuristics suggest it would improve performance for large datasets.
3. Review `src/graph/query_builder.py` to ensure `OPTIONAL MATCH` is used only when necessary, minimizing Cartesian products.

**Verification:**

```bash
# Verify the cypher script syntax (visual check or dry-run if possible)
cat scripts/setup_indexes.cypher
```

After completing this prompt, proceed to **Final Verification**.

---

## 6. Final Steps

**Directive:** Run the final verification.

**Actions:**

1. Check that all files (`docker-compose.monitoring.yml`, `docs/user_manual.md`, `setup_indexes.cypher`) were created.
2. Run `uv run pytest` (if applicable) to ensure no regressions.
3. Print the following completion message:

```text
ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.
```
