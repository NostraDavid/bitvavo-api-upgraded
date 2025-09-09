# Bitvavo API Upgraded – AI Coding Agent Instructions

This project is a **typed, modular, and tested Python SDK** for the Bitvavo cryptocurrency exchange, featuring both a legacy monolithic API and a modern, agent-based architecture. It is designed for reliability, extensibility, and developer ergonomics.

## Architecture Overview

- **Two main API entry points:**
	- `Bitvavo` (legacy, monolithic, in `src/bitvavo_api_upgraded/bitvavo.py`): REST & WebSocket, direct dict/list returns, callback-based WS.
	- `BitvavoClient` (modern, in `src/bitvavo_client/facade.py`): Modular, testable, supports dependency injection, orchestrates endpoint agents.
- **Agent pattern:** Each major concern (public/private endpoints, transport, rate limiting, signing, settings, schema, DataFrame conversion) is a separate agent/module. See `AGENTS.md` for a full list and responsibilities.
- **Settings:** Pydantic-based, loaded from `.env` or environment, with strict validation. See `src/bitvavo_api_upgraded/settings.py` and `src/bitvavo_client/core/settings.py`.
- **Testing:** Defensive, with many tests skipped for risky or flaky API operations. See `tests/` and `tests/bitvavo_api_upgraded/conftest.py` for market filtering and skip logic.

## Key Developer Workflows

- **Install dependencies:**
	```bash
	uv sync
	```
- **Run all tests (multi-version):**
	```bash
	uv run tox
	```
- **Debug tests:**
	```bash
	uv run pytest
	```
- **Check coverage:**
	```bash
	uv run coverage run --source=src --module pytest
	uv run coverage report
	```
- **Lint/format/typecheck:**
	```bash
	uv run ruff format
	uv run ruff check --fix --unsafe-fixes
	uv run mypy src/
	```

**Coverage tip:** Always use `--source=src` and ensure `PYTHONPATH` is set to `src` (see `tox.ini`). Do not use `pytest-cov` (breaks VS Code debugging).

## Project-Specific Patterns & Conventions

- **Strict typing:** All code is type-checked with `mypy` (`disallow_untyped_defs=true`). Update `type_aliases.py` for new types.
- **Return types:** REST methods return `dict | list` or error dicts; modern client uses Result types for functional error handling.
- **Rate limiting:** Bitvavo uses a 1000 points/minute system. Always check `getRemainingLimit()` before trading. Managed by `RateLimitManager` agent.
- **Testing:** Many tests are skipped for trading, withdrawals, or flaky endpoints. WebSocket tests are mostly skipped due to instability.
- **DataFrames:** Unified DataFrame conversion via Narwhals, with schemas in `src/bitvavo_client/schemas/` and utils in `src/bitvavo_api_upgraded/dataframe_utils.py`.
- **Settings:** Use Pydantic settings classes for all config. Environment variables: `BITVAVO_APIKEY`, `BITVAVO_APISECRET`, etc.
- **Versioning:** Use `bump-my-version` and update `CHANGELOG.md` before bumping.

## Integration Points

- **Bitvavo API:** REST (`api.bitvavo.com/v2`), WebSocket (`ws.bitvavo.com/v2/`)
- **Key libraries:** `requests`, `websocket-client`, `pydantic-settings`, `returns`, `tox`, `uv`, `ruff`, `mypy`
- **Settings loading:** `.env` file or environment, validated by Pydantic

## Common Gotchas

1. **Coverage:** Must use `--source=src` and set `PYTHONPATH` for src-layout
2. **WebSocket tests:** Unreliable, mostly skipped
3. **Market filtering:** Some API responses include broken markets; tests filter these
4. **VS Code debugging:** Disable `pytest-cov` extension to avoid conflicts
5. **Rate limiting:** Always check before trading

## Key Files & References

- `AGENTS.md`: Full agent/component breakdown
- `src/bitvavo_api_upgraded/bitvavo.py`: Legacy API class
- `src/bitvavo_client/facade.py`: Modern client facade
- `src/bitvavo_client/endpoints/`: Public/private endpoint agents
- `src/bitvavo_client/auth/`: Rate limiting & signing
- `src/bitvavo_api_upgraded/settings.py`, `src/bitvavo_client/core/settings.py`: Settings
- `src/bitvavo_api_upgraded/dataframe_utils.py`: DataFrame conversion
- `tests/`: Defensive, skip-heavy test suite

---
For more details, see `AGENTS.md` and in-code docstrings. When in doubt, mirror the structure and patterns of existing agents and tests.
