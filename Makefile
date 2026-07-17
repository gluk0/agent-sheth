.PHONY: help install sync run test lint format type-check clean-pycache clean-build clean dev all

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)Available targets:$(NC)"
	@echo "  $(GREEN)install$(NC)      - Sync dependencies with uv"
	@echo "  $(GREEN)run$(NC)         - Run the scaffold application"
	@echo "  $(GREEN)test$(NC)        - Run pytest tests"
	@echo "  $(GREEN)lint$(NC)        - Run ruff linter checks"
	@echo "  $(GREEN)format$(NC)      - Format code with ruff"
	@echo "  $(GREEN)type-check$(NC)  - Run mypy type checker"
	@echo "  $(GREEN)clean$(NC)       - Clean all cache and build artifacts"
	@echo "  $(GREEN)clean-pycache$(NC) - Clean __pycache__ directories"
	@echo "  $(GREEN)clean-build$(NC) - Clean build artifacts"
	@echo "  $(GREEN)dev$(NC)         - Install and set up development environment"
	@echo "  $(GREEN)all$(NC)         - Run lint, type-check, and test"

install:
	uv sync

sync: install

run:
	uv run scaffold

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

type-check:
	uv run mypy src/

clean-pycache:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

clean-build:
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .mypy_cache/ .ruff_cache/
	rm -rf .pytest_cache/
	rm -rf htmlcov/ .coverage

clean: clean-pycache clean-build
	@echo "$(GREEN)✓ Cleaned pycache, build artifacts, and caches$(NC)"

dev: install
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "  Run: make test, make lint, make format, make type-check"

all: lint type-check test
	@echo "$(GREEN)✓ All checks passed!$(NC)"
