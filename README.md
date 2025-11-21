# Gemini Workflow - Production-Ready Q&A System

Enterprise-grade workflow system for evaluating and rewriting Q&A responses using Google Gemini AI.

## ✨ Features

- 🤖 **Intelligent Query Generation** - Automatically generates queries from OCR text
- 📊 **Multi-Candidate Evaluation** - Evaluates multiple answer candidates with scoring
- ✍️ **Answer Rewriting** - Refines selected answers for optimal quality
- 💰 **Cost Tracking** - Real-time token usage and cost calculation
- 🛡️ **Production Hardening** - Rate limiting, type guards, hallucination detection
- 🎨 **Professional UX** - Rich-based presentation layer with clean output separation
- 🧪 **Full Test Coverage** - pytest suite with dependency injection support

## 🏗️ Architecture

```
project_root/
├── .env                    # Environment variables (API keys)
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── UV_GUIDE.md            # Fast package manager guide
├── templates/             # Jinja2 templates
│   ├── prompt_eval.j2
│   ├── prompt_query_gen.j2
│   ├── prompt_rewrite.j2
│   ├── query_gen_user.j2
│   └── rewrite_user.j2
├── data/
│   ├── inputs/            # Input files (OCR, candidates)
│   └── outputs/           # Generated outputs
├── src/                   # Source code package
│   ├── __init__.py
│   ├── agent.py           # Gemini API agent
│   ├── config.py          # Configuration management
│   ├── data_loader.py     # Data loading utilities
│   ├── logging_setup.py   # Logging configuration
│   ├── main.py            # Main workflow orchestrator
│   ├── models.py          # Pydantic models
│   └── utils.py           # Utility functions
└── tests/                 # Test suite
    ├── __init__.py
    ├── test_agent.py
    └── test_dependency_injection.py
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

### 2. Installation

#### Option A: Using pip (Standard)

```bash
# Clone or download the project
cd shining-quasar

# Install dependencies
pip install -r requirements.txt
```

#### Option B: Using uv (Recommended - 10-100x faster)

```bash
# Install uv
pip install uv

# Install dependencies
uv pip install -r requirements.txt
```

See [UV_GUIDE.md](UV_GUIDE.md) for more details.

### 3. Configuration

Create a `.env` file in the project root:

```bash
# Required
GEMINI_API_KEY=your_api_key_here

# Optional (with defaults)
GEMINI_MODEL_NAME=gemini-1.5-pro
GEMINI_MAX_OUTPUT_TOKENS=8192
GEMINI_TIMEOUT=120
GEMINI_MAX_CONCURRENCY=5
GEMINI_CACHE_SIZE=100
```

### 4. Prepare Input Files

Place your input files in `data/inputs/`:

**OCR Text** (`data/inputs/input_ocr.txt`):

```
Your OCR extracted text here...
```

**Candidate Answers** (`data/inputs/input_candidates.json`):

```json
{
  "A": "First candidate answer...",
  "B": "Second candidate answer...",
  "C": "Third candidate answer..."
}
```

### 5. Run the Workflow

```bash
# Run with default settings
python -m src.main

# Run in CHAT mode with custom intent
python -m src.main --mode CHAT --intent "Summarize the key points"

# Specify custom input files
python -m src.main --ocr-file custom_ocr.txt --cand-file custom_candidates.json
```

## 📊 Example Output

```
INFO     리소스 로드 중...
INFO     Rate limiter enabled: 60 requests/minute
INFO     워크플로우 시작 (Mode: AUTO)
INFO     질의 생성 중...
INFO     Token Usage - Prompt: 3,095, Response: 45, Total: 4,929
INFO     질의 생성 완료...
INFO     후보 평가 중...
INFO     Token Usage - Prompt: 4,908, Response: 282, Total: 7,123
INFO     후보 선정 완료: A
INFO     답변 재작성 중...
INFO     Token Usage - Prompt: 3,681, Response: 867, Total: 6,316

🤖 Query: Summarize the key points...
📊 Selected Candidate: A

╭─ 📝 Final Output ──────────────────────────╮
│ # Summary                                  │
│                                            │
│ The key points are:                        │
│ 1. Point one...                            │
│ 2. Point two...                            │
╰────────────────────────────────────────────╯

╭─ Cost Summary ─────────────────────────────╮
│ 💰 Total Session Cost: $0.0534 USD        │
│ 📊 Token Usage: 11,684 input / 1,194 out  │
╰────────────────────────────────────────────╯
```

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 🛠️ Development

### Project Structure

- **`src/agent.py`** - Core Gemini API interaction with retry logic, rate limiting, and cost tracking
- **`src/models.py`** - Pydantic models with hallucination detection
- **`src/config.py`** - Environment-based configuration with deployment flexibility
- **`src/logging_setup.py`** - Separated logging (Rich for console, plain for files)
- **`src/data_loader.py`** - Input data loading with type guards
- **`src/utils.py`** - Utility functions for parsing and file I/O

### Key Features

#### 1. Hallucination Detection

Automatically validates that the LLM's claimed "best candidate" matches actual scores:

```python
@model_validator(mode='after')
def validate_best_candidate(self):
    actual_best = max(self.evaluations, key=lambda x: x.score)
    if self.best_candidate != actual_best.candidate_id:
        logger.warning("LLM Hallucination Detected - Auto-correcting")
        self.best_candidate = actual_best.candidate_id
```

#### 2. Dual Rate Control

- **Semaphore**: Limits concurrent API calls (spatial control)
- **Rate Limiter**: Limits requests per minute (temporal control)
- Prevents `429 Too Many Requests` errors

#### 3. Dependency Injection

Fully testable architecture with mock support:

```python
# Production
agent = GeminiAgent(config, jinja_env=real_env)

# Testing
agent = GeminiAgent(config, jinja_env=mock_env)
```

## 📝 Environment Variables

| Variable                   | Default          | Description                   |
| -------------------------- | ---------------- | ----------------------------- |
| `GEMINI_API_KEY`           | _Required_       | Your Gemini API key           |
| `GEMINI_MODEL_NAME`        | `gemini-1.5-pro` | Model to use                  |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192`           | Maximum output tokens         |
| `GEMINI_TIMEOUT`           | `120`            | API timeout in seconds        |
| `GEMINI_MAX_CONCURRENCY`   | `5`              | Max concurrent requests       |
| `PROJECT_ROOT`             | _Auto_           | Project root (for deployment) |

## 🔒 Production Features

- ✅ **Type Safety** - Pydantic models with `Literal` types
- ✅ **Error Handling** - Multi-layer exception handling with graceful degradation
- ✅ **Rate Limiting** - Dual control (concurrency + RPM)
- ✅ **Cost Tracking** - Real-time token usage and cost calculation
- ✅ **Logging** - Separated console (Rich) and file (plain) logging
- ✅ **Testing** - Full test suite with DI support
- ✅ **Validation** - Fail-fast input validation and hallucination detection

## 📚 Documentation

- **[walkthrough.md](walkthrough.md)** - Detailed implementation walkthrough
- **[UV_GUIDE.md](UV_GUIDE.md)** - Fast package manager guide
- **[task.md](task.md)** - Development task checklist

## 🤝 Contributing

This is a production-ready template. Feel free to fork and customize for your needs.

## 📄 License

MIT License - Use freely in your projects.

## 🙏 Acknowledgments

Built with:

- [Google Gemini AI](https://ai.google.dev/)
- [Pydantic](https://docs.pydantic.dev/)
- [Rich](https://rich.readthedocs.io/)
- [Tenacity](https://tenacity.readthedocs.io/)

---

**Made with ❤️ for production use**
