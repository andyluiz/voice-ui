# Makefile

VENV = $(shell git rev-parse --show-toplevel)/.venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
COVERAGE = $(VENV)/bin/coverage

# A utility function similar to wildcard but that can search recursively
rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))

SRCS=$(call rwildcard,voice_ui,*.py) $(call rwildcard,tools,*.py) $(call rwildcard,tests,*.py)

all: checks tests

checks: format lint

venv:
	python -m venv --upgrade $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

.PHONY: install
install:
	@echo Installing dependencies into $(VENV)
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -e .

.PHONY: help
help:
	@echo "voice_ui Makefile"
	@echo
	@echo "Usage: make [target]"
	@echo
	@echo "Targets:"
	@echo "  help           Show this help message"
	@echo "  venv           Create/upgrade virtual environment (.venv)"
	@echo "  install        Install dependencies into the virtualenv"
	@echo "  format         Format code (black)"
	@echo "  lint           Run linters (ruff)"
	@echo "  type-check     Run static type checks (mypy)"
	@echo "  tests          Run unit tests with coverage"
	@echo "  clean          Clean build artifacts"
	@echo "  docs           Generate docs (doxygen)"

.PHONY: black
black:
	@echo Running black
	$(VENV)/bin/black --check --exclude .venv .

.PHONY: ruff
ruff:
	@echo Running ruff
	$(VENV)/bin/ruff check . --exclude .venv

.PHONY: format
format:
	@echo Formatting with black
	$(VENV)/bin/black --exclude .venv .

.PHONY: lint
lint:
	@echo Running ruff
	$(VENV)/bin/ruff check . --exclude .venv

.PHONY: type-check
type-check:
	@echo Running mypy
	$(VENV)/bin/mypy .

.PHONY: tests
tests:
	@echo Running tests
	$(COVERAGE) erase
	$(COVERAGE) run -m unittest discover -v
	$(COVERAGE) report --omit='tests/*.py' -m -i --fail-under=90
	$(COVERAGE) html -i

.PHONY: online_tests
online_tests:
	@echo Running online tests
	$(COVERAGE) erase
	$(COVERAGE) run --omit='tests/*.py' -m unittest discover -p 'integrated_test_*.py' -v
	$(COVERAGE) report -m -i

# Usage example: make test TEST_FILE=tests/utils/test_memory.py
TEST_FILE :=
.PHONY: test
test:
	@echo Running tests
	$(COVERAGE) run --omit='tests/*.py' -m unittest -v $(subst /,.,$(basename $(TEST_FILE)))
	$(COVERAGE) report -m -i --fail-under=90

.PHONY: compile
compile:
	$(PYTHON) -m py_compile $(SRCS)

clean:
	find ./voice_ui ./examples ./tests ./tools -type d -name '__pycache__' -exec rm -rf {} \;
	rm -rf docs/doxygen
	rm -rf htmlcov .coverage

.PHONY: docs
docs:
	rm -rf docs/doxygen
	doxygen
