.DEFAULT_GOAL := help

UV ?= uv
UV_PYTHON ?=
PYTHON ?= python3
PACKAGE ?=
COVERAGE_FAIL_UNDER ?= 80
TEST_ARGS ?=
RUN = $(if $(UV_PYTHON),UV_PYTHON=$(UV_PYTHON)) $(UV) run

.PHONY: all help bootstrap install install-all install-dev install-test install-test-extras check verify verify-fast live-test skill-test skill-package diff-check lint format-check format fix type-check dependency-check workflow-check manifest-check test test-serial test-parallel coverage build package-check package-verify hooks clean

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Prepare this checkout and install locked dependencies
	$(PYTHON) scripts/worktree_bootstrap.py --uv "$(UV)"

install: install-all ## Install all development dependencies

install-all: ## Install every optional dependency group
	$(UV) sync --all-groups --locked

install-dev: ## Install dependencies for static checks
	$(UV) sync --group dev --locked

install-test: ## Install dependencies for tests
	$(UV) sync --group test --locked $(if $(UV_PYTHON),--python $(UV_PYTHON))

install-test-extras: ## Install optional test utilities
	$(UV) sync --group test --group test-extras --locked $(if $(UV_PYTHON),--python $(UV_PYTHON))

all: verify ## Run the complete verification suite

check: diff-check lint format-check type-check dependency-check workflow-check ## Run fast, non-mutating code checks

verify-fast: check test manifest-check build skill-package ## Run checks without live network requests

verify: verify-fast live-test ## Run all checks, including live Reuters data

diff-check: ## Check the diff for whitespace errors
	git diff --check

lint: ## Check code with Ruff
	$(RUN) ruff check

format-check: ## Check formatting with Ruff
	$(RUN) ruff format --check

format: ## Format code with Ruff
	$(RUN) ruff format

fix: ## Apply Ruff lint fixes and formatting
	$(RUN) ruff check --fix
	$(RUN) ruff format

type-check: ## Check static types with ty
	$(RUN) ty check

dependency-check: ## Check dependency declarations with Deptry
	$(RUN) deptry .

workflow-check: ## Audit GitHub Actions workflows with Zizmor
	$(RUN) zizmor .github/workflows

manifest-check: ## Check source distribution contents
	$(RUN) check-manifest

test: ## Run tests serially
	$(RUN) pytest -m "not integration" $(TEST_ARGS)

test-serial: test ## Run tests without parallel workers

test-parallel: ## Run independent tests with parallel workers
	$(RUN) pytest -m "not integration" -n auto $(TEST_ARGS)

live-test: ## Run live Reuters data checks
	$(RUN) pytest -m integration $(TEST_ARGS)

skill-test: ## Check Skill metadata, instructions, fixtures, and entrypoints
	$(RUN) pytest tests/test_skill_contract.py $(TEST_ARGS)
	$(RUN) reuters-climate-paragraph --help >/dev/null
	$(RUN) rcp --help >/dev/null

skill-package: ## Build the portable Claude Skill archive
	$(RUN) python scripts/package_skill.py dist/reuters-climate-paragraph.skill

coverage: ## Enforce coverage for PACKAGE
	@test -n "$(PACKAGE)" || { echo "Set PACKAGE to the library import name."; exit 2; }
	$(RUN) pytest -m "not integration" $(TEST_ARGS) --cov="$(PACKAGE)" --cov-branch --cov-report=term-missing:skip-covered --cov-fail-under="$(COVERAGE_FAIL_UNDER)"

build: ## Build source and wheel distributions
	rm -rf dist
	$(UV) build --sdist --wheel
	$(RUN) twine check dist/*

package-check: ## Build, install, and import PACKAGE in an isolated environment
	@test -n "$(PACKAGE)" || { echo "Set PACKAGE to the library import name."; exit 2; }
	@temp_dir=$$(mktemp -d); trap 'rm -rf "$$temp_dir"' EXIT; \
	$(UV) build --wheel --out-dir "$$temp_dir/dist"; \
	$(RUN) check-wheel-contents "$$temp_dir"/dist/*.whl; \
	$(UV) venv --no-project "$$temp_dir/venv"; \
	$(UV) pip install --python "$$temp_dir/venv/bin/python" "$$temp_dir"/dist/*.whl; \
	cd "$$temp_dir" && "$$temp_dir/venv/bin/python" -c 'import importlib; importlib.import_module("$(PACKAGE)")'

package-verify: package-check coverage ## Run package import and coverage checks

hooks: ## Run all pre-commit hooks (may modify files)
	$(RUN) pre-commit run --all-files

clean: ## Remove generated files and caches
	rm -rf build dist .coverage htmlcov .pytest_cache .ruff_cache .ty
	find . -maxdepth 1 -type d -name "*.egg-info" -prune -exec rm -rf {} +
	find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
