#!/bin/bash
# Generate API documentation using Sphinx

set -e

DOCS_DIR="docs"
API_DIR="$DOCS_DIR/api"

# Create API directory if not exists
mkdir -p "$API_DIR"

# Generate API documentation from source
sphinx-apidoc -f -o "$API_DIR" src/ \
    --separate \
    --module-first \
    -H "API Reference" \
    -A "shining-quasar Team"

# Build HTML documentation
cd "$DOCS_DIR"
make html

echo "Documentation generated: docs/_build/html/index.html"
