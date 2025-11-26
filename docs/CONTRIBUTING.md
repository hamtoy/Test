# Contributing to Shining Quasar

We welcome contributions! Please follow these guidelines.

## Development Setup

1. **Install dependencies**:

    ```bash
    uv sync --dev
    ```

2. **Install pre-commit hooks**:

    ```bash
    pre-commit install
    ```

## Testing

Run tests before submitting a PR:

```bash
pytest
```

## Code Style

We use `ruff` for linting and formatting.

```bash
ruff check .
ruff format .
```

## Pull Request Process

1. Create a new branch for your feature or fix.
2. Add tests for your changes.
3. Ensure all tests pass.
4. Submit a PR with a clear description.

## Deprecation Policy

When removing or renaming features, follow the deprecation process:

1. Add a warning in the old code.
2. Add a shim if moving files.
3. Document in `DEPRECATION.md`.
