# Contributing to Shining Quasar

Thank you for your interest in contributing to Shining Quasar! This document provides guidelines for setting up your environment, running tests, and submitting pull requests.

## Environment Setup

We use `uv` for fast and reliable package management.

1.  **Install `uv`** (if not already installed):

    ```bash
    pip install uv
    ```

2.  **Sync Dependencies**:

    ```bash
    uv sync
    ```

    This will create a virtual environment and install all dependencies defined in `pyproject.toml`.

3.  **Activate Virtual Environment**:
    - Windows: `.venv\Scripts\activate`
    - Linux/macOS: `source .venv/bin/activate`

## Running Tests

We use `pytest` for testing. Ensure all tests pass before submitting a PR.

```bash
pytest
```

To run tests with coverage:

```bash
pytest --cov=src
```

## Code Style

- **Type Hints**: We enforce type hints for all function signatures.
- **Pydantic**: Use Pydantic models for data validation and configuration.
- **Asyncio**: Use `async/await` for I/O-bound operations.
- **Logging**: Use the `src.logging_setup` module for logging. Do not use `print` statements.

## Documentation

To build the documentation locally:

1.  Navigate to the `docs` directory:
    ```bash
    cd docs
    ```
2.  Build HTML documentation:
    ```bash
    make html
    # or on Windows
    make.bat html
    ```
3.  Open `_build/html/index.html` in your browser.

## Pull Request Process

1.  Fork the repository and create a new branch for your feature or fix.
2.  Ensure all tests pass and code follows the style guidelines.
3.  Submit a Pull Request with a clear description of your changes.
