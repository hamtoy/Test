## [3.0.0] - Unreleased

### ⚠️ BREAKING CHANGES

- **Removed 24 shim files** - All deprecated import paths removed
- Import paths **must** use package structure (e.g., `src.core.models` instead of `src.models`)
- Python 3.10+ now required (dropped 3.9 support)

### Added

- Pure package-based architecture (100%)
- v3.0 readiness verification script (`scripts/verify_v3_readiness.py`)
- Shim removal script with backup support (`scripts/remove_shims_v3.py`)
- Breaking changes documentation (`docs/BREAKING_CHANGES_v3.md`)
- Enhanced type hints across all modules

### Changed

- `src/__init__.py` now exports only public API
- Stricter mypy checks (no `type: ignore` in core modules)

### Removed

- All 24 backward-compatibility shim files:
  - `adaptive_difficulty.py` → `features/difficulty.py`
  - `advanced_context_augmentation.py` → `processing/context_augmentation.py`
  - `cache_analytics.py` → `caching/analytics.py`
  - `caching_layer.py` → `caching/layer.py`
  - `config.py` → `config/settings.py`
  - `constants.py` → `config/constants.py`
  - `data_loader.py` → `processing/loader.py`
  - `dynamic_template_generator.py` → `processing/template_generator.py`
  - `exceptions.py` → `config/exceptions.py`
  - `graph_enhanced_router.py` → `routing/graph_router.py`
  - `graph_schema_builder.py` → `graph/`
  - `integrated_qa_pipeline.py` → `qa/pipeline.py`
  - `lats_searcher.py` → `features/lats.py`
  - `list_models.py` → `llm/list_models.py`
  - `logging_setup.py` → `infra/logging.py`
  - `memory_augmented_qa.py` → `qa/memory_augmented.py`
  - `models.py` → `core/models.py`
  - `multi_agent_qa_system.py` → `qa/multi_agent.py`
  - `multimodal_understanding.py` → `features/multimodal.py`
  - `neo4j_utils.py` → `infra/neo4j.py`
  - `qa_generator.py` → `qa/generator.py`
  - `qa_rag_system.py` → `qa/rag_system.py`
  - `qa_system_factory.py` → `qa/factory.py`
  - `real_time_constraint_enforcer.py` → `infra/constraints.py`
  - `self_correcting_chain.py` → `features/self_correcting.py`
  - `utils.py` → `infra/utils.py`
  - `worker.py` → `infra/worker.py`
- Deprecated environment variables (see MIGRATION.md)

### Migration Guide

See [docs/BREAKING_CHANGES_v3.md](docs/BREAKING_CHANGES_v3.md)

---

## [2.5.0] - Unreleased

### Added
- Enhanced deprecation warning system with improved visibility (`src/_deprecation.py`)
  - `EnhancedDeprecationWarning` class that bypasses Python's default warning filters
  - `warn_deprecated()` function for consistent deprecation messaging
  - `DEPRECATION_LEVEL` environment variable support (normal/strict/verbose)
- Pre-commit hook for deprecated import detection (`scripts/check_deprecated_imports.py`)
- Comprehensive tests for enhanced deprecation system (`tests/test_enhanced_deprecation.py`)
- Updated DEPRECATION.md with v2.5 features, FAQ, and examples

## [Unreleased]
- Add Neo4j health check utility
- Improve type hints and docstrings
- Add mocked integration test for IntegratedQualitySystem
- Measure vector search latency in QA graph helper
- Add logging for LCEL/cross-validation fallbacks and cache stats failures
- Narrow cache manifest error handling in agent/main

