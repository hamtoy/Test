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

