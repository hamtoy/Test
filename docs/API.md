# API Reference

## Agent Package (`src.agent`)

### GeminiAgent

Main AI agent for interacting with Gemini models.

```python
from src.agent import GeminiAgent

agent = GeminiAgent(config=config)
result = agent.run(prompt="Your prompt here")
```

#### Methods

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `run(prompt)` | Execute agent with prompt | `prompt: str` | `str` |
| `get_total_cost()` | Get total API cost | None | `float` |
| `reset()` | Reset agent state | None | None |

---

## Config Package (`src.config`)

### AppConfig

Application configuration dataclass.

```python
from src.config import AppConfig

config = AppConfig(
    model_name="gemini-1.5-flash",
    temperature=0.7,
    max_tokens=1000,
)
```

### Constants

```python
from src.config.constants import ERROR_MESSAGES, LOG_MESSAGES
```

---

## Infra Package (`src.infra`)

### Utils

```python
from src.infra.utils import clean_markdown_code_block, safe_json_parse
```

### Logging

```python
from src.infra.logging import setup_logging, log_metrics
```
