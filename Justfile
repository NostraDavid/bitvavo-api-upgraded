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
    uv run --locked ruff check src tests scripts

dependency-check:
    uv run --locked deptry src/

contract-check:
    python scripts/check_bitvavo_contract.py

format:
    uv run --locked ruff format src tests scripts

format-check:
    uv run --locked ruff format --check src tests scripts

test:
    #!/usr/bin/env bash
    set -euo pipefail
    test_dir="$(mktemp -d)"
    trap 'rm -rf "$test_dir"' EXIT
    cd "$test_dir"
    for setting_name in "${!BITVAVO_@}"; do unset "$setting_name"; done
    uv run --project "{{justfile_directory()}}" --locked pytest --ignore="{{justfile_directory()}}/tests/bitvavo_client/endpoints/test_public.py" -p no:dotenv -o addopts= --tb=short -q -c "{{justfile_directory()}}/pyproject.toml" "{{justfile_directory()}}/tests/bitvavo_client" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_dataframe_utils.py" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_helper_funcs.py" "{{justfile_directory()}}/tests/bitvavo_api_upgraded/test_settings.py"

build:
    uv build

check: format-check dependency-check test build

hooks:
    uv run --locked prek install
