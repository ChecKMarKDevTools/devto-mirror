# Dev.to Mirror Development Commands

# Prefer the project's venv python if present, otherwise fall back to system `python`.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)

.PHONY: help install test lint format clean check ai-checks security
.PHONY: check-complexity

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	uv sync --locked --group dev
	# Ensure lefthook is executed via uv so we use the pinned dev toolchain
	# Skip lefthook installation in CI environments (GITHUB_ACTIONS, CI)
	@if [ -z "$$CI$$GITHUB_ACTIONS" ]; then uv run lefthook install; fi

test:  ## Run unit tests
	uv run coverage run --source src -m unittest discover -s tests -p 'test_*.py'
	uv run coverage report --fail-under=85
	uv run coverage html

lint:  ## Run linting checks (formatting, linting, security)
	uv run isort --check-only --profile black --line-length 120 src/ tests/ scripts/
	uv run flake8 src/ tests/ scripts/
	uv run python scripts/validate_site_generation.py

format:  ## Format code with Black
	uv run black src/ tests/ scripts/ --line-length 120

prechecks:  ## Run prechecks on staged files (applies formatting to staged files only)
	@./scripts/prechecks.sh $$(git diff --name-only --cached)

prechecks-full:  ## Run full prechecks across the repo (force full run)
	@./scripts/prechecks.sh $$(git ls-files)

security:  ## Run security checks
	uv run bandit -r scripts src/ -ll -iii
	@if [ "$$CI" = "true" ] || [ "$$GITHUB_ACTIONS" = "true" ] || [ "$$PIP_AUDIT" = "1" ]; then \
		uv run python scripts/run_pip_audit.py; \
	else \
		echo "Skipping pip-audit (set PIP_AUDIT=1 to enable locally)"; \
	fi
	uv run python scripts/check_detect_secrets.py

check-complexity:  ## Check cognitive complexity (max 15)
	@echo "🔍 Checking cognitive complexity (max 15)..."
	@uv run radon cc scripts/ src/ -s 2>/dev/null | grep -E "\(((1[6-9])|([2-9][0-9])|([1-9][0-9]{2,}))\)" && \
		echo "❌ Functions with complexity >15 found. See docs/COMPLEXITY_REFACTORING.md" && exit 1 || \
		echo "✅ All functions within complexity limits"

ai-checks:  ## Single command: format → lint → security → complexity → test + site (POC ready)
	@set -e; \
	echo "🔍 format → lint → security → complexity → test"; \
	$(MAKE) format && echo "  ✓ format" || (echo "  ✗ format"; exit 1); \
	$(MAKE) lint && echo "  ✓ lint" || (echo "  ✗ lint"; exit 1); \
	$(MAKE) security && echo "  ✓ security" || (echo "  ✗ security"; exit 1); \
	$(MAKE) check-complexity && echo "  ✓ complexity" || (echo "  ✗ complexity (see docs/COMPLEXITY_REFACTORING.md)"; exit 1); \
	$(MAKE) test && echo "  ✓ test" || (echo "  ✗ test"; exit 1); \
	echo "✅ Ready to commit."

clean:  ## Clean up generated files
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf __pycache__/
	rm -rf .mypy_cache/
	rm -rf .pytest_cache/
	rm -rf src/devto_mirror.egg-info/
	rm -rf dist/
	rm -rf build/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
