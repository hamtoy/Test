# vulture_whitelist.py
# Intentionally unused code that should not be flagged by vulture.
# This file lists code that appears unused but is actually required.

# Ignore this file from analysis
pass  # noqa

# ============================================================================
# Pydantic model fields and validators
# Used by Pydantic framework, not called directly
# ============================================================================
_.cache_size  # src/config/settings.py - Pydantic field
_.enable_data2neo  # src/config/settings.py - Pydantic field
_.model_config  # src/config/settings.py - Pydantic field
_.max_input_tokens  # src/config/constants.py - exported constant
_.validate_api_key  # Pydantic field_validator
_.validate_concurrency  # Pydantic field_validator
_.validate_timeout  # Pydantic field_validator
_.validate_temperature  # Pydantic field_validator
_.validate_cache_ttl  # Pydantic field_validator
_.validate_budget  # Pydantic field_validator
_.validate_log_level  # Pydantic field_validator
_.validate_cache_stats_max_entries  # Pydantic field_validator
_.validate_cache_min_tokens  # Pydantic field_validator
_.enforce_single_model  # Pydantic model_validator
_.model_post_init  # Pydantic hook
_.validate_best_candidate  # Pydantic validator

# ============================================================================
# Lazy import mechanisms (__getattr__ and __dir__)
# Used for deprecation warnings and lazy loading
# ============================================================================
__getattr__  # Lazy import pattern in multiple __init__.py files
__dir__  # Lazy import pattern in multiple __init__.py files

# ============================================================================
# Protocol/Interface methods (abstract methods implemented by subclasses)
# ============================================================================
_.raw_response  # GenerationResult dataclass field
_.final_output  # WorkflowState dataclass field
_.success  # WorkflowState dataclass field
_.create_nodes  # GraphProvider interface method
_.create_relationships  # GraphProvider interface method
_._register_atexit  # Internal Neo4j registration

# ============================================================================
# Pydantic dataclass fields in entities
# ============================================================================
_.source_text  # Entity dataclass field
_.organization  # Entity dataclass field

# ============================================================================
# Context manager protocol variables (required by Python)
# ============================================================================
exc_type  # __exit__ protocol
tb  # __exit__ protocol  
__context  # BaseSettings context

# ============================================================================
# Callback/handler methods (called by LangChain framework)
# ============================================================================
_.on_llm_start  # LangChain callback
_.on_llm_end  # LangChain callback
_.on_chain_error  # LangChain callback
_.serialized  # callback argument

# ============================================================================
# Public API methods (exposed but may not be used internally)
# ============================================================================
_.get_stats  # Redis cache API method
_.get_statistics  # Budget/extractor API method
_.is_budget_exceeded  # Budget API method
_.cleanup_expired  # Cache manager API method
_.store_cache  # Cache manager API method
_.load_cached  # Cache manager API method
_._cleanup_expired_cache  # Agent core internal method
_.invalidate_cache  # Caching layer API method
_.get_rules_cached  # Caching layer API method
_.validate_output  # Pipeline validation method
_.validate_session  # RAG system method

# ============================================================================
# Batch processor public API
# ============================================================================
_.to_dict  # BatchJob serialization method
_.get_job  # BatchJobManager API
_.list_jobs  # BatchJobManager API
_.cancel_job  # BatchJobManager API
_.create_batch_job  # BatchJobManager API
_.submit_batch_job  # BatchJobManager API
_.poll_batch_job  # BatchJobManager API
_.create_batch_request  # BatchJobManager API
_.cleanup_completed_jobs  # BatchJobManager API

# ============================================================================
# LLM methods
# ============================================================================
_.rewrite  # GeminiClient API method
_.embed_documents  # DummyEmbeddings method
_.generate_ultimate_qa  # LangChainQASystem API

# ============================================================================
# Feature modules
# ============================================================================
_.stream_with_validation  # ConstraintEnforcer API
_.ask_with_memory  # MemoryAugmentedQA API
_.suggest_next_query_type  # Autocomplete feature
_.suggest_constraint_compliance  # Autocomplete feature
_.generate_qa_with_all_enhancements  # QualityEnhancer API

# ============================================================================
# Graph extractor methods
# ============================================================================
_.extract_entities  # Data2NeoExtractor API
_.write_to_graph  # Data2NeoExtractor API
_.document_id  # Local variable used in context

# ============================================================================
# Worker module
# ============================================================================
_.MODEL_COST_PER_TOKEN  # Worker cost constant
_.error_type  # Error handling
_.enforcer  # QualityEnhancer attribute

# ============================================================================
# Backwards-compatible classes
# ============================================================================
RateLimitManager  # Backwards-compatible alias class
