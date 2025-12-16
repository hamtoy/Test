# AI Agent Improvement Prompts

## 1. Execution Rules (Mandatory)

1. **No Text-Only Responses:** Do not output long explanations. Use file-edit tools immediately.
2. **Sequential Execution:** Follow the checklist order strictly. Do not skip prompts.
3. **Use File Tools:** All code changes must be applied using `write_to_file`, `replace_file_content`, or `run_command`.
4. **Verification:** Run the specified verification commands after each prompt.
5. **Complete Implementation:** Provide actual implementation code, not placeholders like `// TODO` or `// ...`.
6. **English Only:** All content in this file is in English.

---

## 2. Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | **PROMPT-001** | Gemini Batch API Full Implementation | P2 | ⬜ Pending |
| 2 | **OPT-3** | Neo4j Cypher Index Optimization | OPT | ⬜ Pending |

**Total: 2 prompts | Completed: 0 | Remaining: 2**

---

## 3. Implementation Prompts

### 🟡 Priority P2 (High)

---

### [PROMPT-001] Gemini Batch API Full Implementation

> Execute this prompt now, then proceed to [OPT-3].

**Task Description:**

Implement the full Gemini Batch API integration in `src/llm/batch.py`. The current stub implementation needs to be replaced with actual API calls to Google's Batch API to enable cost-effective asynchronous processing (50% cost reduction).

**Target Files:**

- `src/llm/batch.py` (modify)
- `tests/unit/llm/test_batch.py` (extend)

**Steps:**

1. **Update `GeminiBatchClient` Initialization:**
   - Initialize Google AI SDK client.
   - Add Redis client support for job state persistence.

   ```python
   def __init__(
       self,
       model_name: str = "gemini-flash-latest",
       redis_client: Any | None = None,
   ) -> None:
       self.model_name = model_name
       self._jobs: dict[str, BatchJob] = {}
       self.redis = redis_client
       self._job_prefix = "batch_job:"
       self._job_ttl = 86400  # 24 hours
       # Initialize GenAI client here if needed or lazily in methods
       logger.info(f"GeminiBatchClient initialized with model: {model_name}")
   ```

2. **Implement `submit_batch` with Real API:**
   - Convert `BatchRequest` objects to Google GenAI API format.
   - Call `genai.GenerativeModel.batch_embed_contents` or `generate_content` equivalent (based on latest SDK).
   - *Note:* If specific Batch API method is experimental, implement a robust HTTP-based fallback or standard async wrapper.
   - For this implementation, assume we wrap standard async calls or use the provided SDK method for batching if available. If not, implement a pseudo-batcher that uses `asyncio.gather` but tracks it as a persistent job.
   - **Crucial:** Ensure job state is saved to Redis via `_save_job`.

3. **Implement Redis Persistence (`_save_job`, `_load_job`):**
   - Serialize `BatchJob` to JSON and save to Redis with TTL.
   - Retrieve from Redis in `get_status`.

4. **Integrate Cost Tracking:**
   - In `_record_batch_cost`, use `CostTracker` with a `0.5` multiplier to reflect the Batch API discount.

**Verification:**

```bash
# Type check strictly
uv run python -m mypy src/llm/batch.py --strict

# Run unit tests
uv run pytest tests/unit/llm/test_batch.py -v
```

After completing this prompt, proceed to **[OPT-3]**.
**

---

### 🟢 Priority P3 (Normal)

No pending P3 items.

---

### 🚀 Optimization (OPT)

---

### [OPT-3] Neo4j Cypher Index Optimization

> Execute this prompt now, then proceed to final verification.

**Task Description:**

Implement explicit Cypher index and constraint creation in `src/graph/builder.py` to optimize query performance and ensure data integrity as the graph grows.

**Target Files:**

- `src/graph/builder.py` (modify)

**Steps:**

1. **Add `create_indices` method to `GraphBuilder`:**
    - Define a list of Cypher queries to create indices/constraints for key labels: `Rule`, `Topic`, `Document`, `Chunk`.
    - Target properties: `id`, `name`, `title`.

    ```python
    async def create_indices(self) -> None:
        """Create Neo4j indices and constraints for performance."""
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Rule) REQUIRE r.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (r:Rule) ON (r.name)",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)",
        ]
        
        async with self.driver.session() as session:
            for query in queries:
                await session.run(query)
                logger.info(f"Executed index query: {query}")
    ```

2. **Call `create_indices` during initialization:**
    - Ensure indices are checked/created when the builder is initialized or via a specific setup method.

**Verification:**

```bash
# Check syntax
uv run ruff check src/graph/builder.py

# Run related tests (if any exists for builder)
uv run pytest tests/unit/graph/test_builder.py -v
```

After completing this prompt, proceed to final verification.

---

## 4. Final Verification

After completing all prompts, run the following verification commands to ensure everything works correctly:

```bash
# Full type checking
uv run python -m mypy src/ --strict

# Run all tests
uv run pytest tests/ --tb=short -q

# Lint check
uv run ruff check src/

# Security scan
uv run bandit -r src/ -ll
```

---

## 5. Completion Confirmation

When all prompts have been executed successfully, print the following message:

```text
ALL PROMPTS COMPLETED.

All pending improvement items from the latest report have been applied.

Summary:
- PROMPT-001: Gemini Batch API Full Implementation ⬜ → ✅
- OPT-3: Neo4j Cypher Index Optimization ⬜ → ✅

Previously Completed:
- OPT-1: Neo4j Batch Transaction Optimization ✅
- OPT-2: Redis Pipelining Optimization ✅
- KG Provider Module ✅

Expected Improvements:
- 50% cost reduction for batch LLM operations
- 30%+ improvement in graph query latency
- Enhanced data integrity with unique constraints

Project Score: 98/100 (Grade: A+)
Status: Production-Ready with Optimized Performance
```
