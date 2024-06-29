# Makefile

VENV = $(shell git rev-parse --show-toplevel)/.venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
COVERAGE = $(VENV)/bin/coverage

# A utility function similar to wildcard but that can search recursively
rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))

SRCS=$(call rwildcard,tests,*.py)

all: checks tests

checks: flake8

.PHONY: flake8
flake8:
	@echo Running flake8
	$(VENV)/bin/flake8 .

.PHONY: tests
tests:
	@echo Running tests
	$(COVERAGE) erase
	$(COVERAGE) run -m unittest discover -v
	$(COVERAGE) report -m -i --fail-under=75
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
	$(COVERAGE) report -m -i --fail-under=75

.PHONY: compile
compile:
	$(PYTHON) -m py_compile $(SRCS)

clean:
	find ./ -type d -name '__pycache__' -exec rm -rf {} \;
	rm -rf docs/doxygen
	rm -rf htmlcov

.PHONY: docs
docs:
	rm -rf docs/doxygen
	doxygen
