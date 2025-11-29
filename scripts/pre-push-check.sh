#!/bin/bash
set -e

echo "=========================================="
echo "🔍 Pre-Push Quality Check"
echo "=========================================="

# 1. Formatting
echo ""
echo "📐 Checking code formatting..."
ruff format --check src/ tests/ || {
    echo "❌ Format check failed. Run: ruff format src/ tests/"
    exit 1
}

# 2. Linting
echo ""
echo "🔎 Linting code..."
ruff check src/ tests/ || {
    echo "❌ Lint check failed. Run: ruff check --fix src/ tests/"
    exit 1
}

# 3. Type checking
echo ""
echo "🔒 Type checking..."
mypy src/ || {
    echo "❌ Type check failed. Fix type errors."
    exit 1
}

# 4. Tests
echo ""
echo "🧪 Running tests..."
pytest tests/ --cov=src --cov-fail-under=80 -q || {
    echo "❌ Tests failed or coverage < 80%"
    exit 1
}

# 5. Security
echo ""
echo "🔐 Checking for secrets..."
if command -v detect-secrets &> /dev/null; then
    detect-secrets scan || {
        echo "⚠️  Potential secrets detected"
    }
fi

echo ""
echo "=========================================="
echo "✅ All checks passed!"
echo "=========================================="
