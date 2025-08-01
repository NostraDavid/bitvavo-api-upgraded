# Bitvavo API Upgraded - AI Coding Assistant Instructions

## Project Overview
This is a **typed, tested, and enhanced** Python wrapper for the Bitvavo cryptocurrency exchange API. It's an "upgraded" fork of the official Bitvavo SDK with comprehensive type hints, unit tests, and improved developer experience.

## Architecture & Key Components

### Core API Structure
- **Main class**: `Bitvavo` in `src/bitvavo_api_upgraded/bitvavo.py` - handles both REST and WebSocket operations
- **Dual API pattern**: REST methods return dict/list data directly; WebSocket methods use callbacks
- **WebSocket facade**: `WebSocketAppFacade` nested class provides WebSocket functionality with reconnection logic
- **Settings system**: Pydantic-based configuration in `src/bitvavo_api_upgraded/settings.py`

### Project Layout (src-layout)
```
src/bitvavo_api_upgraded/    # Source code
├── __init__.py              # Main exports
├── bitvavo.py              # Core API class (~3600 lines)
├── settings.py             # Pydantic settings
├── helper_funcs.py         # Utility functions
└── type_aliases.py         # Type definitions
tests/                      # Comprehensive test suite
```

## Development Workflows

### Essential Commands
```bash
# Development setup
uv sync                     # Install all dependencies
uv run tox                  # Run full test suite across Python versions

# Testing & Coverage
uv run pytest              # Run tests with debugging support
uv run coverage run --source=src --module pytest  # Coverage with proper src-layout
uv run coverage report     # View coverage results

# Code Quality
uv run ruff format         # Format code
uv run ruff check          # Lint code
uv run mypy src/           # Type checking
```

### Coverage Configuration Notes
- Uses `coverage.py` instead of `pytest-cov` (breaks VS Code debugging)
- Requires `--source=src` for src-layout projects
- `tox.ini` sets `PYTHONPATH={toxinidir}/src` for proper module resolution

## Project-Specific Patterns

### Testing Strategy
- **Defensive testing**: Many tests skip risky operations (`@pytest.mark.skipif` for trading methods)
- **API flakiness**: Tests handle inconsistent Bitvavo API responses (see `conftest.py` market filtering)
- **WebSocket challenges**: Entire `TestWebsocket` class skipped due to freezing issues
- **Mock patterns**: Use `pytest-mock` for time functions and external dependencies

### Type System & Error Handling
- **Strict typing**: `mypy` configured with `disallow_untyped_defs=true`
- **Return types**: Methods return `dict | list` for success, `errordict` for API errors
- **Type aliases**: Custom types like `ms` (milliseconds), `anydict` in `type_aliases.py`

### Rate Limiting & Authentication
- **Weight-based limits**: Bitvavo uses 1000 points/minute, tracked in `rateLimitRemaining`
- **Settings pattern**: Use `BitvavoSettings` for API config, `BitvavoApiUpgradedSettings` for extras
- **Environment variables**: Load via `.env` file with `BITVAVO_APIKEY`/`BITVAVO_APISECRET`

### Versioning & Release
- **Semantic versioning**: Automated with `bump-my-version`
- **Changelog-first**: Update `CHANGELOG.md` with `$UNRELEASED` token before version bumps
- **GitHub Actions**: Automated publishing on tag creation

## Code Quality Standards

### Linting Configuration
- **Ruff**: Replaces black, isort, flake8 with `select = ["ALL"]` and specific ignores
- **Line length**: 120 characters consistently across tools
- **Test exemptions**: Tests ignore safety checks (`S101`), magic values (`PLR2004`)

### Documentation Patterns
- **Extensive docstrings**: WebSocket methods include JSON response examples
- **Rate limit documentation**: Each method documents its weight cost
- **API mirroring**: Maintains parity with official Bitvavo API documentation

## Integration Points

### External Dependencies
- **Bitvavo API**: REST at `api.bitvavo.com/v2`, WebSocket at `ws.bitvavo.com/v2/`
- **Key libraries**: `requests` (REST), `websocket-client` (WS), `pydantic-settings` (config)
- **Development tools**: `tox` (multi-version testing), `uv` (dependency management)

### Configuration Management
- **Pydantic settings**: Type-safe config loading from environment/`.env`
- **Dual settings classes**: Separate original vs. enhanced functionality
- **Validation**: Custom validators for log levels, rate limits

## Common Gotchas

1. **Coverage setup**: Must use `--source=src` and set `PYTHONPATH` for src-layout
2. **WebSocket testing**: Currently unreliable, most WS tests are skipped
3. **Market filtering**: Some API responses include broken markets that tests filter out
4. **VS Code debugging**: Disable `pytest-cov` extension to avoid conflicts with `coverage.py`
5. **Rate limiting**: Always check `getRemainingLimit()` before making API calls

## When Making Changes

- **Add tests**: Follow the defensive testing pattern, skip risky operations
- **Update types**: Maintain strict typing, update `type_aliases.py` if needed
- **Consider API changes**: This wrapper mirrors Bitvavo's API structure closely
- **Version bumps**: Update `CHANGELOG.md` first, then use `bump-my-version`
