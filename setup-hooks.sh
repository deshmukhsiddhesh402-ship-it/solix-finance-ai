#!/bin/bash
# Setup pre-commit hooks for Solix
# Usage: bash ./setup-hooks.sh

set -e

echo "🔧 Setting up pre-commit hooks..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip install pre-commit
fi

# Install git hooks
pre-commit install
pre-commit install --hook-type commit-msg

echo "✓ Pre-commit hooks installed"
echo ""
echo "Next steps:"
echo "1. cd solix_minimal"
echo "2. Commit a file to test: git add . && git commit -m 'test'"
echo ""
echo "To run manually: pre-commit run --all-files"
