.PHONY: lint format check test install-dev clean conda-env conda-activate

# Command definitions
PYTHON = python
PIP = $(PYTHON) -m pip
DJANGO = $(PYTHON) manage.py
BLACK = black
ISORT = isort
FLAKE8 = flake8
PYLINT = pylint
MYPY = mypy

# Directories to exclude from linting/formatting
EXCLUDE = migrations __pycache__ venv env .venv .* */\.*

# Define space and comma for substitution
comma := ,
space :=
space +=

# Default targets
all: check

# Install development dependencies
install-dev:
#	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install black isort flake8 pylint mypy

# Lint code with all linters
lint:
	@echo "Running flake8..."
	$(FLAKE8) . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=migrations,__pycache__,venv,env,.venv,.*,*/\.*
	$(FLAKE8) . --count --exit-zero --max-line-length=127 --statistics --exclude=migrations,__pycache__,venv,env,.venv,.*,*/\.*
	@echo "Running pylint..."
	$(PYTHON) -m pylint --fail-under 8 --rcfile=.pylintrc .
	@echo "Running black..."
	$(BLACK) --check --line-length 120 . --exclude "/(\..*|migrations|__pycache__|venv|env|.conda|\.venv)/"
	@echo "Checking imports with isort..."
	$(ISORT) --check --diff . --skip-glob="*/\.*" --skip-glob="*/migrations/*" --skip-glob="*/__pycache__/*" --skip-glob="*/venv/*" --skip-glob="*/env/*" --skip-glob="*/.venv/*" --skip-glob="*/.conda/*"
	@echo "Running mypy type checking..."
	$(MYPY) --ignore-missing-imports ./ --exclude="(migrations|__pycache__|venv|env|.conda|\.venv)"

# Format code with Black and isort
format:
	@echo "Formatting with Black..."
	$(BLACK) --line-length 120 . --exclude "/(\..*|migrations|__pycache__|venv|env|.conda|\.venv)/"
	@echo "Sorting imports with isort..."
	$(ISORT) . --skip-glob="*/\.*" --skip-glob="*/migrations/*" --skip-glob="*/__pycache__/*" --skip-glob="*/venv/*" --skip-glob="*/env/*" --skip-glob="*/.venv/*" --skip-glob="*/.conda/*"

# Run Django tests
test:
	@echo "Running Django tests..."
	$(DJANGO) test

# Check everything (full CI pipeline simulation)
check: lint test
	@echo "All checks passed!"

# Clean up Python cache files
clean:
	@echo "Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Show help
help:
	@echo "Available targets:"
	@echo "  install-dev : Install development dependencies"
	@echo "  lint        : Run all linters"
	@echo "  format      : Format code with Black and isort"
	@echo "  test        : Run Django tests"
	@echo "  check       : Run all checks (lint + test)"
	@echo "  clean       : Remove cache files"
	@echo "  help        : Show this help message"