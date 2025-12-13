# 🔍 LATS (Language Agent Tree Search) Guide

> This guide explains how to use the LATS (Language Agent Tree Search) module for enhanced Q&A quality through tree-based exploration and self-correction.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Usage Examples](#usage-examples)
4. [Performance Tuning](#performance-tuning)
5. [Advanced Features](#advanced-features)

---

## Overview

LATS (Language Agent Tree Search) is an advanced search algorithm that explores multiple answer candidates in a tree structure, evaluates them, and selects the best option through iterative refinement.

### Key Features

- **Tree-based Exploration**: Expands multiple candidate answers in parallel
- **UCT Selection**: Uses Upper Confidence Bound for Trees (UCT) algorithm for node selection
- **Self-Correction**: Reflects on errors and generates improved alternatives
- **Budget Tracking**: Monitors token and cost usage during search
- **Graph Validation**: Optionally validates actions against knowledge graph constraints

### When to Use LATS

- Complex questions requiring multiple refinements
- High-value responses where quality outweighs compute cost
- Scenarios with clear evaluation criteria for ranking answers

---

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_LATS` | bool | `false` | Enable/disable LATS search mode |

### Programmatic Configuration

The `LATSSearcher` class accepts the following parameters:

```python
from src.features.lats import LATSSearcher, SearchState

searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    graph_validator=None,           # Optional: Knowledge graph validator
    propose_actions=None,           # Optional: Custom action proposer
    evaluate_action=None,           # Optional: Custom action evaluator
    budget_tracker=None,            # Optional: Budget tracking instance
    max_visits=10,                  # Maximum visits per node
    max_depth=3,                    # Maximum tree depth
    exploration_constant=1.414,     # UCT exploration constant (sqrt(2))
    token_budget=10000,             # Token budget limit
    cost_budget=1.0,                # Cost budget limit (USD)
)
```

### Parameter Details

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| `max_visits` | Controls search thoroughness | 5-20 |
| `max_depth` | Maximum tree exploration depth | 2-5 |
| `exploration_constant` | Balances exploration vs. exploitation | 1.0-2.0 |
| `token_budget` | Maximum tokens to consume | 5000-50000 |
| `cost_budget` | Maximum cost in USD | 0.1-5.0 |

---

## Usage Examples

### Basic Usage with Environment Variable

```bash
# Enable LATS in your .env file
ENABLE_LATS=true
```

```python
import os
os.environ["ENABLE_LATS"] = "true"

# The inspection workflow will automatically use LATS when enabled
from src.workflow.inspection import inspect_answer

result = await inspect_answer(
    question="What is the capital of France?",
    answer="Paris is the capital.",
    agent=your_agent,
)
```

### Direct LATS Searcher Usage

```python
from src.features.lats import LATSSearcher, SearchState
from src.core.interfaces import LLMProvider

# Initialize with your LLM provider
searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    max_visits=10,
    max_depth=3,
    token_budget=10000,
)

# Create initial state
initial_state = SearchState(turns=[])

# Run the search
best_node = await searcher.run(initial_state)

# Get the result
if best_node.result:
    print(f"Best answer: {best_node.action}")
    print(f"Score: {best_node.reward}")
```

### With Custom Evaluation

```python
async def custom_evaluator(node):
    """Custom evaluator that scores based on specific criteria."""
    answer = node.action
    score = 0.0
    
    # Example: Score based on answer length and keywords
    if len(answer) > 100:
        score += 0.3
    if "because" in answer.lower():
        score += 0.2
    if "therefore" in answer.lower():
        score += 0.2
    
    return score

searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    evaluate_action=custom_evaluator,
    max_visits=15,
)

result = await searcher.run()
```

---

## Performance Tuning

### Balancing Quality vs. Speed

| Setting | Quality Focus | Speed Focus |
|---------|---------------|-------------|
| `max_visits` | 15-20 | 3-5 |
| `max_depth` | 4-5 | 2 |
| `exploration_constant` | 2.0 | 1.0 |
| `token_budget` | 30000+ | 5000 |

### Cost Optimization

```python
# Conservative settings for cost-conscious usage
searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    max_visits=5,           # Fewer visits
    max_depth=2,            # Shallow search
    token_budget=5000,      # Tight token budget
    cost_budget=0.5,        # Strict cost limit
)
```

### High-Quality Settings

```python
# Premium settings for best results
searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    max_visits=20,          # Thorough exploration
    max_depth=5,            # Deep search
    exploration_constant=1.8,  # Balanced exploration
    token_budget=50000,     # Generous budget
    cost_budget=5.0,        # Allow higher cost
)
```

---

## Advanced Features

### SearchState Management

The `SearchState` class tracks the conversation history and budget:

```python
from src.features.lats import SearchState

# Create a state with existing conversation
state = SearchState(
    turns=[
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI is..."},
    ],
    cumulative_tokens=150,
    cumulative_cost=0.01,
)

# Add a new turn (returns new immutable state)
new_state = state.add_turn("The updated answer is...")

# Update budget tracking
new_state = new_state.update_budget(tokens=100, cost=0.005)

# Generate cache key for deduplication
cache_key = state.hash_key()
```

### Graph Validation

Integrate with a knowledge graph to validate actions:

```python
async def kg_validator(state: SearchState, action: str) -> ValidationResult:
    """Validate action against knowledge graph constraints."""
    # Check if the action contradicts known facts
    if contradicts_knowledge_graph(action):
        return ValidationResult(
            allowed=False,
            reason="Contradicts known facts",
            penalty=0.5,
        )
    return ValidationResult(allowed=True, penalty=0.0)

searcher = LATSSearcher(
    llm_provider=your_llm_provider,
    graph_validator=kg_validator,
)
```

### Error Reflection

LATS can reflect on errors to improve subsequent attempts:

```python
# The searcher automatically reflects on errors
reflection = await searcher.reflect_on_error(
    error="The answer was too vague",
    context="User asked for specific details about the process",
)
# Returns: "The previous response lacked specificity. Focus on..."
```

---

## Related Documentation

- [Configuration Guide](./CONFIG_GUIDE.md)
- [Workflow Guide](./WORKFLOW_GUIDE.md)
- [API Reference](./API_REFERENCE.md)

---

## Troubleshooting

### LATS Not Activating

1. Verify `ENABLE_LATS=true` in your `.env` file
2. Restart the application after changing environment variables
3. Check logs for initialization messages

### High Cost with LATS

1. Reduce `max_visits` and `max_depth`
2. Set stricter `token_budget` and `cost_budget`
3. Consider using LATS only for high-value queries

### Slow Response Times

1. Use lower `max_visits` (3-5)
2. Reduce `max_depth` to 2
3. Enable parallel action validation (default)
