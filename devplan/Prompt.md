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
| 1 | **PROMPT-001** | Gemini Batch API Full Implementation | P2 | ⬜ Pending |
| 2 | **OPT-1** | Neo4j Batch Transaction Optimization | OPT | ⬜ Pending |
| 3 | **OPT-2** | Redis Pipelining Optimization | OPT | ⬜ Pending |

**Total: 3 prompts | Completed: 0 | Remaining: 3**

---

## 3. Implementation Prompts

### [PROMPT-001] Gemini Batch API Full Implementation

> Execute this prompt now, then proceed to OPT-1.

**Task Description:**

Implement the full Gemini Batch API integration in `src/llm/batch.py`. The current stub implementation needs to be replaced with actual API calls to Google's Batch API for high-throughput, cost-effective processing.

**Target Files:**

- `src/llm/batch.py` (modify)
- `tests/unit/llm/test_batch.py` (extend)

**Steps:**

1. **Update `GeminiBatchClient.__init__`:**
   - Add configuration for Batch API endpoint
   - Initialize Google AI SDK client
   - Add Redis client for persistent job state storage

2. **Implement `submit_batch` method:**

   ```python
   async def submit_batch(
       self,
       requests: list[BatchRequest],
       model_name: str | None = None,
   ) -> BatchJob:
       """Submit batch job to Gemini Batch API."""
       import google.generativeai as genai
       
       # Create batch request payload
       batch_requests = [
           {
               "contents": [{"parts": [{"text": req.prompt}]}],
               "generationConfig": {"temperature": req.temperature}
           }
           for req in requests
       ]
       
       # Submit to Batch API
       model = genai.GenerativeModel(model_name or self.model_name)
       batch_response = await model.generate_content_batch(batch_requests)
       
       job_id = f"batch_{uuid.uuid4().hex[:12]}"
       job = BatchJob(
           job_id=job_id,
           status=BatchJobStatus.RUNNING,
           created_at=datetime.now(),
           model_name=model_name or self.model_name,
           total_requests=len(requests),
       )
       
       # Persist to Redis
       await self._save_job(job)
       
       return job
   ```

3. **Add Redis persistence methods:**

   ```python
   async def _save_job(self, job: BatchJob) -> None:
       """Persist job state to Redis."""
       import json
       job_data = {
           "job_id": job.job_id,
           "status": job.status.value,
           "created_at": job.created_at.isoformat(),
           "model_name": job.model_name,
           "total_requests": job.total_requests,
           "completed_requests": job.completed_requests,
       }
       await self.redis.set(
           f"batch_job:{job.job_id}",
           json.dumps(job_data),
           ex=86400  # 24 hour TTL
       )
   
   async def _load_job(self, job_id: str) -> BatchJob | None:
       """Load job state from Redis."""
       import json
       data = await self.redis.get(f"batch_job:{job_id}")
       if not data:
           return None
       job_data = json.loads(data)
       return BatchJob(
           job_id=job_data["job_id"],
           status=BatchJobStatus(job_data["status"]),
           created_at=datetime.fromisoformat(job_data["created_at"]),
           model_name=job_data["model_name"],
           total_requests=job_data["total_requests"],
           completed_requests=job_data["completed_requests"],
       )
   ```

4. **Update `get_status` and `get_results`:**
   - Load job from Redis instead of memory
   - Poll Gemini Batch API for status updates

5. **Add cost tracking integration:**

   ```python
   from src.agent.cost_tracker import record_batch_cost
   
   # After batch completion
   await record_batch_cost(
       model_name=job.model_name,
       total_tokens=total_tokens,
       cost_multiplier=0.5  # 50% discount for batch
   )
   ```

6. **Extend tests in `tests/unit/llm/test_batch.py`:**
   - Add tests for Redis persistence
   - Add tests for API integration (use mocks)
   - Add tests for error handling

**Verification:**

```bash
# Run type checking
uv run python -m mypy src/llm/batch.py

# Run batch-specific tests
uv run pytest tests/unit/llm/test_batch.py -v

# Run lint check
uv run ruff check src/llm/batch.py
```

**After completing this prompt, proceed to [OPT-1].**

---

### [OPT-1] Neo4j Batch Transaction Optimization

> Execute this prompt now, then proceed to OPT-2.

**Task Description:**

Optimize Neo4j graph building operations in `src/graph/builder.py` by replacing individual `session.run()` calls with batch transactions using `UNWIND` patterns as recommended by Neo4j best practices.

**Target Files:**

- `src/graph/builder.py` (modify)
- `tests/unit/graph/test_builder.py` (extend if exists)

**Steps:**

1. **Identify batch opportunities in `src/graph/builder.py`:**
   - Find loops that call `session.run()` for each item
   - Group related operations into batch collections

2. **Implement batch node creation:**

   ```python
   def create_rules_batch(self, rules: list[dict]) -> None:
       """Create multiple Rule nodes in a single transaction."""
       query = """
           UNWIND $batch AS item
           MERGE (r:Rule {id: item.id})
           SET r.text = item.text,
               r.category = item.category,
               r.updated_at = datetime()
       """
       with self.driver.session() as session:
           session.run(query, batch=rules)
           logger.info(f"Created {len(rules)} Rule nodes in batch")
   ```

3. **Implement batch relationship creation:**

   ```python
   def create_relationships_batch(
       self,
       relationships: list[dict]
   ) -> None:
       """Create multiple relationships in a single transaction."""
       query = """
           UNWIND $batch AS rel
           MATCH (a {id: rel.from_id})
           MATCH (b {id: rel.to_id})
           MERGE (a)-[r:RELATES_TO]->(b)
           SET r.type = rel.type
       """
       with self.driver.session() as session:
           session.run(query, batch=relationships)
   ```

4. **Refactor existing methods to use batch operations:**
   - Replace `for` loops with batch collection and single query
   - Maintain backward compatibility with existing API

5. **Add performance logging:**

   ```python
   import time
   
   def create_graph_batch(self, data: dict) -> dict:
       """Build graph with batch operations."""
       start = time.perf_counter()
       
       # Batch operations
       self.create_rules_batch(data.get("rules", []))
       self.create_constraints_batch(data.get("constraints", []))
       self.create_examples_batch(data.get("examples", []))
       
       elapsed = time.perf_counter() - start
       logger.info(f"Graph build completed in {elapsed:.2f}s")
       
       return {"elapsed_seconds": elapsed, "items_processed": len(data)}
   ```

**Verification:**

```bash
# Run type checking
uv run python -m mypy src/graph/builder.py

# Run graph tests
uv run pytest tests/unit/graph/ -v

# Run lint check
uv run ruff check src/graph/builder.py
```

**After completing this prompt, proceed to [OPT-2].**

---

### [OPT-2] Redis Pipelining Optimization

> Execute this prompt now, then proceed to final verification.

**Task Description:**

Optimize Redis cache operations in `src/caching/redis_cache.py` by implementing pipelining for batch operations, reducing network round-trips for multi-key operations.

**Target Files:**

- `src/caching/redis_cache.py` (modify)
- `tests/unit/caching/test_redis_cache.py` (extend)

**Steps:**

1. **Add `get_many` method with pipelining:**

   ```python
   async def get_many(self, keys: list[str]) -> dict[str, Any | None]:
       """Get multiple values in a single round-trip."""
       if not keys:
           return {}
       
       async with self.redis.pipeline() as pipe:
           for key in keys:
               pipe.get(f"{self.prefix}{key}")
           results = await pipe.execute()
       
       return {
           key: self._deserialize(result)
           for key, result in zip(keys, results)
       }
   ```

2. **Add `set_many` method with pipelining:**

   ```python
   async def set_many(
       self,
       items: dict[str, Any],
       ttl: int | None = None
   ) -> None:
       """Set multiple values in a single round-trip."""
       if not items:
           return
       
       expire = ttl or self.default_ttl
       
       async with self.redis.pipeline() as pipe:
           for key, value in items.items():
               pipe.set(
                   f"{self.prefix}{key}",
                   self._serialize(value),
                   ex=expire
               )
           await pipe.execute()
       
       logger.debug(f"Set {len(items)} keys in batch")
   ```

3. **Add `delete_many` method:**

   ```python
   async def delete_many(self, keys: list[str]) -> int:
       """Delete multiple keys in a single round-trip."""
       if not keys:
           return 0
       
       async with self.redis.pipeline() as pipe:
           for key in keys:
               pipe.delete(f"{self.prefix}{key}")
           results = await pipe.execute()
       
       deleted = sum(1 for r in results if r)
       return deleted
   ```

4. **Add serialization helpers:**

   ```python
   def _serialize(self, value: Any) -> str:
       """Serialize value for Redis storage."""
       import json
       return json.dumps(value)
   
   def _deserialize(self, data: bytes | None) -> Any | None:
       """Deserialize value from Redis."""
       import json
       if data is None:
           return None
       return json.loads(data)
   ```

5. **Add tests for batch operations:**

   ```python
   @pytest.mark.asyncio
   async def test_get_many(redis_cache):
       # Setup
       await redis_cache.set("key1", "value1")
       await redis_cache.set("key2", "value2")
       
       # Test
       results = await redis_cache.get_many(["key1", "key2", "key3"])
       
       # Verify
       assert results["key1"] == "value1"
       assert results["key2"] == "value2"
       assert results["key3"] is None
   ```

**Verification:**

```bash
# Run type checking
uv run python -m mypy src/caching/redis_cache.py

# Run caching tests
uv run pytest tests/unit/caching/test_redis_cache.py -v

# Run lint check
uv run ruff check src/caching/redis_cache.py
```

**After completing this prompt, proceed to final verification.**

---

## 4. Final Verification

After completing all prompts, run the following verification commands to ensure everything works correctly:

```bash
# Full type checking
uv run python -m mypy src/

# Run all tests
uv run pytest tests/ --tb=short -q

# Lint check
uv run ruff check src/

# Security scan
uv run bandit -r src/ -ll
```

---

## 5. Completion Confirmation

```text
ALL PROMPTS COMPLETED.

All pending improvement and optimization items from the latest report have been applied.

Summary:
- PROMPT-001: Gemini Batch API Full Implementation ⬜ → ✅
- OPT-1: Neo4j Batch Transaction Optimization ⬜ → ✅
- OPT-2: Redis Pipelining Optimization ⬜ → ✅

Expected Improvements:
- 50% cost reduction for batch LLM operations
- 30-50% faster graph building operations
- 60-80% reduced latency for multi-key cache operations

Project Score: 95/100 (Grade: A)
Status: Production-Ready with Performance Optimizations Applied
```
