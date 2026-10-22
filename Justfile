set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

sync:
    uv sync --locked

update:
    devenv update
    uv lock --upgrade
    uv sync --locked

lint:
    uv run --locked ruff check src tests

format:
    uv run --locked ruff format src tests

format-check:
    uv run --locked ruff format --check src tests

test:
    #!/usr/bin/env bash
    set -euo pipefail
    test_dir="$(mktemp -d)"
    trap 'rm -rf "$test_dir"' EXIT
    cd "$test_dir"
    for setting_name in "${!BITVAVO_@}"; do unset "$setting_name"; done
    uv run --project "{{justfile_directory()}}" --locked pytest --ignore="{{justfile_directory()}}/tests/bitvavo_client/endpoints" -p no:dotenv -o addopts= --tb=short -q -c "{{justfile_directory()}}/pyproject.toml" "{{justfile_directory()}}/tests/bitvavo_client" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_dataframe_utils.py" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_helper_funcs.py" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_settings.py"

build:
    uv build

check: format-check test build

hooks:
    uv run --locked pre-commit install
