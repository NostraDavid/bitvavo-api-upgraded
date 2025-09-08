# Changelog

## v4.1.2 - 2025-09-08

- replace `DATAFRAME` with multiple separate DataFrame models.

## v4.1.1 - 2025-09-07

- actually add bitvavo_client
- add py.typed

## v4.1.0 - 2025-09-07

**NEW ARCHITECTURE**: Modern, modular `bitvavo_client` with type-safe `returns` pattern! 🏗️

This release introduces a completely rewritten client architecture alongside the existing API, providing a modern, type-safe, and highly testable alternative while maintaining full backward compatibility.

### Added

- **🏗️ New `bitvavo_client` Module**: Complete architectural rewrite with modern Python patterns
  - `BitvavoClient` facade providing clean, intuitive API access
  - Separation of concerns with dedicated `PublicAPI` and `PrivateAPI` endpoint classes
  - Built on the `returns` library for functional error handling with `Success`/`Failure` pattern
  - Type-safe throughout with comprehensive Pydantic model validation
  - Configurable response formats: raw dicts, Pydantic models, or DataFrames

- **📊 Enhanced Model System**: Comprehensive Pydantic models for all API responses
  - `public_models.py`: ServerTime, Markets, Assets, OrderBook, Trades, Candles, etc.
  - `private_models.py`: Account, Orders, Trades, Deposits, Withdrawals, etc.
  - Full validation with descriptive error messages
  - Automatic type conversion and constraint checking

- **🔧 Modern Configuration**: Enhanced settings system with `BitvavoSettings`
  - Environment variable integration with `.env` support
  - Type-safe configuration with Pydantic validation
  - Flexible rate limiting and authentication options

- **🧪 Comprehensive Test Suite**: Extensive testing with multiple response format validation
  - Abstract test base classes ensuring consistent API coverage
  - Tests for raw dict, Pydantic model, and DataFrame response formats
  - Parameter validation testing for all endpoints
  - MiCA compliance validation for regulatory reporting endpoints

- **📋 Error Codes Documentation**: Added `docs/html/error_codes.html` with comprehensive Bitvavo API error documentation

### Changed

- **🎯 Enhanced `calc_lag()` Function**: Improved server time calculation using statistical analysis instead of naive timing
- **🐍 Python 3.10+ Target**: Updated Ruff configuration to target Python 3.10 features
- **🔧 Dependency Updates**: Updated various dependencies including:
  - `identify` v2.6.13 → v2.6.14
  - `pyspark` v4.0.0 → v4.0.1
  - `pytest-cov` v6.2.1 → v6.3.0
- **📦 Renamed Internal Functions**: `_default()` renamed to `default()` for consistency
- **🔍 Stricter Type Checking**: Enhanced type hints and made `zip()` calls strict throughout codebase

### Architecture Highlights

**Modern Client Usage**:

```python
from bitvavo_client import BitvavoClient, BitvavoSettings
from bitvavo_client.core.model_preferences import ModelPreference

# Configure client with typed settings
settings = BitvavoSettings()  # Loads from environment/config
client = BitvavoClient(settings, preferred_model=ModelPreference.PYDANTIC)

# Type-safe API calls with functional error handling
result = client.public.markets()
match result:
    case Success(markets):
        for market in markets:
            print(f"{market.market}: {market.status}")
    case Failure(error):
        print(f"API error: {error}")
```

**Key Architectural Improvements**:

- **Functional Error Handling**: No more exception-based error handling; explicit `Success`/`Failure` patterns
- **Type Safety**: Full type coverage with mypy compatibility
- **Modular Design**: Clear separation between transport, authentication, validation, and API logic
- **Testability**: Dependency injection and abstract interfaces enable comprehensive testing
- **Flexibility**: Support for multiple response formats (dict/Pydantic/DataFrame) in the same codebase

### Migration Path

The existing `bitvavo_api_upgraded` module remains **100% unchanged and fully supported**. The new `bitvavo_client` provides a modern alternative:

- **Current users**: No action required - existing code continues to work
- **New projects**: Consider using `bitvavo_client` for improved type safety and error handling
- **Gradual migration**: Both can be used side-by-side during transition

### Files Added/Modified

- **48 Python/config files** added or modified
- **New module structure**: Complete `bitvavo_client/` package with submodules for auth, transport, endpoints, models, etc.
- **Enhanced tooling**: Updated pre-commit hooks, pyproject.toml configuration
- **Documentation**: Error codes reference and architectural documentation

## v4.0.0 - 2025-08-22

### Removed

- Python 3.9 support ends in 2 months. I'm doing it a little early, as I'm going to do a rewrite using the `returns`
  lib, and I'll *need* the `match` statement, which was added by Python 3.10.

## v3.0.0 - 2025-08-22

### Removed

- all camelCase functions and methods are gone-gone. Use `v2.3.0` to fix your code.

## v2.3.0 - 2025-08-22

### Changed

Alright, pay attention - we're deprecating ALL camelCase functions and methods in favour of snake_case.

That means you can use this version to fix your code. Every camelCase function and method will throw a warning, with the
new name in snake_case suggested, but the code will still work just fine.

We're removing the camelCase functions in the next major release.

## v2.2.0 - 2025-08-20

**NEW FEATURE**: Multi-key support and keyless API access! 🔑

This release introduces comprehensive support for multiple API keys and keyless
(public endpoint) API access, making it easier to manage rate limits and access
public data without authentication.

### Added

- **🔑 Multiple API Key Support**: Enhanced authentication system
  - `APIKEYS` configuration option for multiple key/secret pairs
  - Automatic load balancing across multiple API keys for rate limit management
  - Graceful fallback between keys when rate limits are reached
  - Enhanced `BitvavoSettings` class with multi-key validation
- **🌐 Keyless API Access**: Public endpoint support without authentication
  - `PREFER_KEYLESS` setting to prioritize public endpoints over authenticated
    ones
  - Automatic detection of endpoints that don't require authentication
  - Improved rate limit handling for public vs. authenticated requests
- **⚙️ Enhanced Settings System**:
  - More strict type validation with better error messages
  - Default values for all settings with comprehensive type hints
  - `DEFAULT_RATE_LIMIT` configuration for new API keys
  - Improved SSL certificate auto-detection and configuration
- **🧪 Comprehensive Testing Infrastructure**:
  - `pytest-dotenv` integration for environment variable testing
  - New `tests/vars.env` for isolated test configuration
  - Multiple test scenarios for clean environment overrides
  - Extensive integration tests for settings validation
  - Tests for multi-key scenarios and keyless operations

### Changed

- **🔧 Settings Architecture**: Restructured for better maintainability
  - Enhanced field validation with descriptive error messages
  - Improved model validators for API key processing
  - Better separation between core and upgraded settings
- **📦 Development Dependencies**: Added `pytest-dotenv>=0.5.2` for enhanced testing
- **🎯 Rate Limiting Logic**: Improved handling for multiple keys and keyless requests

### Examples

**Multiple API Keys Setup**:

```python
from bitvavo_api_upgraded import Bitvavo
from bitvavo_api_upgraded.settings import bitvavo_settings

# Via environment variables
# BITVAVO_APIKEYS='[{"key": "key1", "secret": "secret1"}, {"key": "key2", "secret": "secret2"}]'

# Or programmatically
bitvavo_settings.APIKEYS = [
    {"key": "your_api_key_1", "secret": "your_api_secret_1"},
    {"key": "your_api_key_2", "secret": "your_api_secret_2"}
]

bitvavo = Bitvavo(**bitvavo_settings.model_dump())
```

**Enhanced Settings Configuration**:

```env
# .env file
BITVAVO_PREFER_KEYLESS=true
BITVAVO_API_UPGRADED_DEFAULT_RATE_LIMIT=750
BITVAVO_API_UPGRADED_PREFER_KEYLESS=false
```

### Performance & Benefits

- **Rate Limit Optimization**: Distribute requests across multiple API keys automatically
- **Public Endpoint Efficiency**: Reduce unnecessary authentication overhead
- **Failover Support**: Automatic switching between API keys when limits are reached
- **Enhanced Reliability**: Better handling of rate limit scenarios

## v2.1.0 - 2025-08-18

**NEW FEATURE**: Comprehensive dataframe support across 10+ libraries using
Narwhals! 🐻‍❄️

This release introduces unified dataframe output support for multiple popular
Python dataframe libraries, allowing you to get API responses directly as
pandas, polars, cudf, dask, and many other dataframe formats.

### Added

- **🐻‍❄️ Universal DataFrame Support**: New `output_format` parameter for all
  data-returning REST methods
  - Supports 10+ dataframe libraries: pandas, polars, cudf, modin, pyarrow,
    dask, duckdb, ibis, pyspark, pyspark-connect, sqlframe
  - Powered by [Narwhals](https://github.com/narwhals-dev/narwhals) for unified
    dataframe API
  - Graceful fallback to dict format when libraries aren't available
- **📊 Enhanced API Methods**: Added `output_format` parameter to:
  - `markets()`: Get market data as dataframes
  - `assets()`: Get asset information as dataframes
  - `candles()`: Get candlestick data as dataframes (specialized handling for
    OHLCV format)
  - `tickerPrice()`: Get ticker prices as dataframes
  - `tickerBook()`: Get ticker book data as dataframes
  - `orders()`: Get order data as dataframes
  - `trades()`: Get trade data as dataframes
  - `transactionHistory()`: Get transaction history as dataframes
  - `depositHistory()`: Get deposit history as dataframes
  - `withdrawalHistory()`: Get withdrawal history as dataframes
  - `accountHistory()`: Get account history as dataframes
  - `reportTrades()`: Get trade reports as dataframes
  - `reportBook()`: Get order book reports as dataframes
- **📋 Enhanced Type System**:
  - New `OutputFormat` enum with all supported formats
  - Exported directly from main package: `from bitvavo_api_upgraded import
    OutputFormat`
  - Full type hints for dataframe return types
- **📦 Optional Dependencies**: Smart dependency management via extras
  - Install specific dataframe support: `pip install
    'bitvavo-api-upgraded[pandas]'`
  - Multiple formats: `pip install 'bitvavo-api-upgraded[pandas,polars,dask]'`

### Changed

- **📚 Enhanced Documentation**: All affected methods now include comprehensive
  dataframe examples
- **🔄 Backward Compatibility**: All existing code continues to work unchanged
  (default is still dict format)
- **⚡ Performance**: Efficient conversion using Narwhals' zero-copy operations
  where possible

### Examples

```python
from bitvavo_api_upgraded import Bitvavo, OutputFormat
from bitvavo_api_upgraded.settings import bitvavo_settings

bitvavo = Bitvavo(**bitvavo_settings.model_dump())

# Get markets as pandas DataFrame
markets_df = bitvavo.markets(output_format=OutputFormat.PANDAS)
print(type(markets_df))  # <class 'pandas.core.frame.DataFrame'>

# Get candlestick data as polars DataFrame
candles_df = bitvavo.candles("BTC-EUR", "1h", output_format=OutputFormat.POLARS)
print(candles_df.columns)  # ['timestamp', 'open', 'high', 'low', 'close', 'volume']

# Get order history as dask DataFrame (distributed)
orders_df = bitvavo.orders("BTC-EUR", output_format=OutputFormat.DASK)
distributed_result = orders_df.compute()

# Traditional dict format still works (default)
markets_dict = bitvavo.markets()  # Returns list[dict] as before
```

### Migration Guide

**No breaking changes** - this is a pure feature addition:

- Existing code using `bitvavo.markets()`, `bitvavo.candles()`, etc. continues
  to work unchanged
- Add `output_format=OutputFormat.PANDAS` (or your preferred format) to get
  dataframes
- Install optional dependencies as needed: `pip install
  'bitvavo-api-upgraded[pandas]'`

### Dependencies

- **New required**: `narwhals>=2.0.0` (lightweight, no extra dependencies)
- **New optional**: Multiple dataframe libraries as extras (pandas, polars,
  cudf, etc.)
- **Development**: Added comprehensive test dependencies for multi-library
  testing

## v2.0.0 - 2025-08-12

**BREAKING CHANGES**: This release includes significant API updates to match the latest Bitvavo API requirements. All trading operations now require an `operatorId` parameter for MiCA compliance.

To be fair, it's not a massive change, but it does require updating your code to
include the new parameter.

Anyway, turns out Bitvavo has been releasing their API changes
[here](https://docs.bitvavo.com/releases/sneak-preview/). Right now, we're
up-to-date with version [2.9.0](https://docs.bitvavo.com/releases/v2.9.0/).

### Added

- **MiCA Compliance Support**: New endpoints for regulatory compliance reporting
  - `reportTrades()`: Generate trade reports for specific date ranges and
    markets
  - `reportBook()`: Generate order book reports for specific date ranges and
    markets
  - `accountHistory()`: Retrieve detailed account transaction history
- **Enhanced Error Handling**: Improved error responses for new compliance
  endpoints
- **Test Coverage**: Comprehensive test suite for new MiCA compliance endpoints
  - `test_account_history()`: Tests account history retrieval
  - `test_report_trades()`: Tests trade reporting functionality (skipped for
    safety)
  - `test_report_book()`: Tests order book reporting functionality (skipped for
    safety)

### Changed

- **BREAKING**: All trading operations now require `operatorId` parameter:
  - `placeOrder()`: Added required `operatorId: int` parameter
  - `updateOrder()`: Added required `operatorId: int` parameter
  - `cancelOrder()`: Added required `operatorId: int` parameter
  - WebSocket equivalents also updated with `operatorId` requirement
- **Enhanced `cancelOrder()`**: Now supports both `orderId` and `clientOrderId` parameters
  - When both are provided, `clientOrderId` takes precedence
  - Maintains backward compatibility with existing `orderId` usage
- **Improved `fees()` Method**: Enhanced documentation and parameter support
  - Better handling of market-specific and quote-specific fee queries
  - Clearer documentation of tier-based fee structures
- **Updated Test Suite**: All trading method tests updated with required `operatorId` parameters
  - Tests remain safely skipped to prevent accidental live trading
  - New defensive testing patterns for MiCA compliance endpoints

### Migration Guide

**For existing trading operations**, update your code to include the `operatorId` parameter:

```python
# Before (v1.17.2 and earlier)
bitvavo.placeOrder(
    market="BTC-EUR",
    side="buy",
    orderType="limit",
    body={"amount": "0.1", "price": "50000"}
)

# After (v2.0.0+)
bitvavo.placeOrder(
    market="BTC-EUR",
    side="buy",
    orderType="limit",
    body={"amount": "0.1", "price": "50000"},
    operatorId=12345  # Your operator ID
)
```

**For MiCA compliance reporting**:

```python
# Generate trade report
trades = bitvavo.reportTrades(
    market="BTC-EUR",
    options={
        "startDate": "2025-01-01T00:00:00.000Z",
        "endDate": "2025-01-31T23:59:59.999Z"
    }
)

# Generate order book report
book_report = bitvavo.reportBook(
    market="BTC-EUR",
    options={
        "startDate": "2025-01-01T00:00:00.000Z",
        "endDate": "2025-01-31T23:59:59.999Z"
    }
)

# Get account history
history = bitvavo.accountHistory(options={})
```

### Notes

- This update brings the wrapper fully up-to-date with Bitvavo's latest API
  requirements
- All changes maintain backward compatibility except for the required
  `operatorId` parameter
- MiCA compliance features require appropriate account permissions
- WebSocket functionality updated consistently with REST API changes

## v1.17.2 - 2025-08-01

Maintenance release, no functional changes. At least not from my side. I do note
the API has changed on Bitvavo's side, but I'll need to cover that soon enough.

### Added

- `copilot-instructions.md`

### Changed

- `structlog` v25 can now be used
- fixed `coverage` reporting
  - it broke; don't know why; solution was to add `coverage combine` to
    `tox.ini`

## v1.17.1 - 2024-12-24

Turns out the settings weren't working as expected, so I switched
`python-decouple` out from `pydantic-settings`, which (once setup) works a lot
smoother. Keywords being "once setup", because holy smokes is it a paint to do
the initial setup - figure out how the hell you need to validate values before
or after, etc.

Just don't forget to create a local `.env` with `BITVAVO_APIKEY` and
`BITVAVO_APISECRET` keys.

### Added

- `pydantic-settings`: a powerful and modern way of loading your settings.
  - we're using `.env` here, but it can be setup for `.json` or `.yaml` -
    whatever you fancy.
  - because of `pydantic-settings` you can now also do
    `Bitvavo(bitvavo_settings.model_dump())`, and import bitvavo_settings from
    `settings.py`
- add pydantic plugin for mypy, so mypy stops complaining about pydantic.
- vscode settings to disable `pytest-cov` during debugging. If you do not
  disable `pytest-cov` during debugging, it still silently break your debugging
  system...
- you can now import BitvavoApiUpgradedSettings and BitvavoSettings directly
  from `bitvavo_api_upgraded`

### Changed

- `python-decouple` replaced by `pydantic-settings` - see Added and Removed
- `pytest-cov` relegated to enable coverage via vscode - friendship with
  `pytest-cov` ended. `coverage.py` is my best friend.
  - reason for this is because `pytest-cov` fucked with the ability to debug
    within vscode.
- bump minor Python versions

### Removed

- `python-decouple` - this lacked type hinting since forever, not to mention it
  didn't throw errors if missing...

### Fixed

- a bunch of tests that have VERY flaky output from the API >:(

## v1.17.0 - 2024-11-24

Integrate all changes from Bitvavo's `v1.1.1` to `v1.4.2` lib versions,
basically catching up their changes with our code. The reason for choosing
`v1.1.1` as starting point, is because I'm not sure if I missed anything,
because if I follow the timeline on PyPI is that I should pick `v1.2.2`, but if
I look at my commit history, I should choose an older point. Oh well, it's only
a little bit more work.

I used [this Github
link](https://github.com/bitvavo/python-bitvavo-api/compare/v1.1.1...v1.4.2) to
compare their versions.

### Added

- `fees()` call. This was added to the Python SDK in early 2024.
- `_default(value, fallback)` function, which ensures a `fallback` is returned,
  if `value` is `None`. This ensures sane values will always be available.
- `strintdict` type, as I had a bunch of `dict` types copied.

### Changed

- you can now do `from bitvavo_api_upgraded import Bitvavo`, instead of `from
  bitvavo_api_upgraded.bitvavo import Bitvavo`, which always felt annoying. You
  can still use the old way; no worries.
- lowercased the http headers like `Bitvavo-Ratelimit-Remaining`, because
  Bitvavo updated the API, which broke this code. This should probably fix the
  issues of older versions of this lib going over the rate limit. 😅
- `LICENSE.txt`'s year got updated
- in `README.md`, below my text, I've replaced their old README with their
  current one.
- fixed coverage report; I switched to `pytest-cov`, from `coverage.py`
  eventhough `pytest-cov` still uses `coverage.py`, but the output was messed up
  (it also covered `tests/`, wich was unintentional)

### Unchanged

Normally I don't add this chapter, but I'm moving changes from Bitvavo's repo to
here, so it's good I'll track this stuff for later.

- I did NOT add the `name` var to `__init__.py`, because I'm pretty sure they
  added it for their build process, but since I'm using `uv` I don't need that.
- Did not add `self.timeout`, as I use `self.ACCESSWINDOW / 1000` instead.

## v1.16.0 - 2024-11-18

Quite a few changes, most aimed at the maintenance of this project, but all
changes are superficial - the functional code has not changed.

### Added

- `ruff`, which replaces `auotflake`, `black`, `flake8`, `isort`, and `pyupgrade`, in both `pyproject.toml` and
  `.pre-commit-config.yaml`
- `from __future__ import annotations`, so I can already use `|` instead of
  `Union`
- `py.typed` to enable mypy support for people who use this lib :)
- `wrap_public_request` to `conftest.py`, so I can more easily fix tests, if a market like `BABYDOGE-EUR` returns broken
  data (missing fields, `None` values, etc)

### Changed

- replaced `pip` with `uv`; I've become a big fan, since I don't have to handle the Python version anymore
  - [uv installation](https://docs.astral.sh/uv/getting-started/installation/) - do prefer the `curl` installation so
    you can `uv self update` and not need to touch your system's Python installation at all!
  - Just `uv sync` to setup the `.venv`, and then `uv run tox` to run tox, or `uv run black` to run black, etc.
- updated dependencies in `pyproject.toml`, and `.pre-commit-config.yaml`
- because we're dropping Python 3.7 and 3.8 support, we can finally use lowercase `list` and `dict`
- fixed a bunch of tests (disabled one with errorCode 400), due to minor API
  changes.
- formatting using `ruff`
- replace the unmaintained `bump2version` with `bump-my-version`

### Removed

- support for Python `3.7`, `3.8`; both EOL since last update
- `check-manifest` (used for `MANIFEST.in`)
- `rich`, as it would force its use on my users, and that's a no-no, as it's WAY
  too verbose. >:(

## v1.15.8 - 2022-03-13

### Changed

- also iso format

## v1.15.7 - 2022-03-13

### Changed

- add currentTime to napping-until-reset log

## v1.15.6 - 2022-03-13

### Changed

- add buffer time to sleep()

## v1.15.5 - 2022-03-13

### Changed

- format targetDatetime

## v1.15.4 - 2022-03-13

### Changed

- same as last one, except also for private calls

## v1.15.3 - 2022-03-13

### Changed

- add targetDatetime to napping-until-reset info log

## v1.15.2 - 2022-03-13

### Changed

- fix not being able to override settings variables

## v1.15.1 - 2022-03-13

### Changed

- fix the rateLimit check for private calls (this was a bug that let you get banned when making too many calls)

## v1.15.0 - 2022-02-09

### Changed

- fix the callback functions, again
- internal `Bitvavo.websocket` is now `Bitvavo.WebSocketAppFacade` (which is a better, more descriptive, name)
- internal `receiveThread` class is now `ReceiveThread`

### Removed

- bug that broke the code, lmao

## v1.14.1 - 2022-02-09

### Changed

- fixed the websocket's callback functions

## v1.14.0 - 2022-02-06

Make `upgraded_bitvavo_api` multi-processing friendly! :D

### Added

- add chapted to PyPI to shortly explain how to change settings for this lib.
- add `BITVAVO_API_UPGRADED_RATE_LIMITING_BUFFER` variable. Default value `25`; Change this to 50 or higher _only_ when
  you keep getting banned, because you're running more than one `Bitvavo` object. If you're only running one `Bitvavo`
  objects, you're probably fine.

## v1.13.2 - 2022-02-06

### Changed

- fixed a bug where I subtracted where I should've added, making 304 errors more likely 😅

## v1.13.1 - 2022-01-29

### Changed

- You will now be informed that you have been temporary banned, even if you did NOT enable the `DEBUGGING` var during
  creation of the `Bitvavo` object. Such a stupid design, originally.

## v1.13.0 - 2022-01-23

### Changed

- fixed the API timeout (which did nothing, client-side), by adding a timeout to the actual API call. If `ACCESSWINDOW`
  is now set (when creating `Bitvavo`) to `2000` ms, it will time-out after `2000` ms, and not wait the full `30_000` ms
  anyway.

## v1.12.0 - 2022-01-21

### Added

- A trigger to nap `Bitvavo` when `rateLimitRemaining` is about run empty, until `rateLimitResetAt` has elapsed and
  `rateLimitRemaining` has reset, after which the API call will continue as normal. ONLY WORKS FOR NORMAL CALLS -
  WEBSOCKET NOT (yet?) SUPPORTED!

## v1.11.5 - 2022-01-19

A `.env` file is just a text file with "equal-separated" key-value pairs. No spaces around the `=` symbol!

### Added

- `calcLag()` to `Bitvavo`, which returns the time difference between the server's clock and your local clock. Set the
  variable 1 line down to the value that comes out of this function :)
- `BITVAVO_API_UPGRADED_LAG=50` option for your `.env` file, to reduce the amount of `304 "Request was not received
within acceptable window"` errors I was getting. Default value of this setting is 50 (milliseconds), but it is better
  if you override it :)
- One or two patch-versions back I added `BITVAVO_API_UPGRADED_EXTERNAL_LOG_LEVEL` as an option, but forgot to mention
  it 😅. This setting covers all loggers that are used by this lib's dependencies (`requests`, which makes use of
  `urllib3`, and `websocket-client` to be a bit more specific). Use this setting to shut them up, by setting the
  variable to `WARNING` or `CRITICAL` 😁

## v1.11.4 - 2022-01-19

### Removed

- duplicate log messages ;)

## v1.11.3 - 2022-01-18

### Changed

- The logger should now be fixed; I wanted all subloggers to get integrated into the struclog style instead of putting
  out some standard text.

## v1.11.2 - 2022-01-16

### Added

- putting `BITVAVO_API_UPGRADED_LOG_LEVEL=DEBUG` into a `.env` file in your client should make this lib spam you with
  log messages.

### Changed

- replaced `python-dotenv` with `python-decouple` lib. This enables us to set default values for settible settings.

## v1.11.1 - 2022-01-16

I ran the unittests this time >\_>

### Changed

- fixed bug where `self.debugging` could not be found in `Bitvavo`

## v1.11.0 - 2022-01-16

### Changed

- all external loggers (urllib3 and websocket being big ones) now all use a fancy format to log! Or at least, they
  should be!
- improved pypi README

## v1.10.0 - 2022-01-15

No more `print()` bullshit! :D

### Added

- classifiers on the pypi page
- a better logging library (structlog). This should enable you to control logging better (while providing better logs!)

## v1.9.0 - 2022-01-15

### Changed

- fixed a critical bug that broke the `Bitvavo` class

## v1.8.3 - 2022-01-15

### Changed

- improve api calls by subtracting some client-server lag; This should make calls more stable
- simplify Bitvavo constructor (doesn't change anything about the external API)
- fix time_to_wait by checking whether curr_time > rateLimitResetAt

### Removed

- rateLimitThread, because it has been a pain in my ass. Using a regular `sleep()` is much better, I noticed.

## v1.8.2 - 2022-01-15

### Changed

- `time_to_wait` now _always_ returns a positive number. I'm getting sick of sleep getting a negative number

## v1.8.1 - 2022-01-15

### Added

- type aliases! You can now use `s`, `ms`, `us`, instead of slapping `int` on everything! float versions `s_f`, `ms_f`
  and `us_f` are also available. You'll likely use `ms` and `s_f` most of the time :)
- helper functions! I added `time_ms` and `time_to_wait` to hide some weird calculations behind functions.

### Changed

- improved the timing calculation and typing of certain values a bit

## v1.8.0 - 2022-01-11

### Changed

- fixed getRemainingLimit - This explains why it NEVER changed from 1000...

## v1.7.0 - 2021-12-31

Documentation now comes built-in! :D

I'll probably find some typo/minor error right after creating this version, but I think for users this is one of the
more important updates, so out it does!

PS: Happy new year! I write this as it's 2021-12-31 23:15. Almost stopping, so I can stuff my face with Oliebollen and
celebrate new year! :D

### Added

- documentation/docstrings for almost every function and method!
- type aliases: `anydict`,`strdict`,`intdict`,`errordict`
- types for `caplog` and `capsys` in all `test_*` function

### Changed

- `candle` wasn't the only wrongly named method. `book` was too. Changed `symbol` argument to `market`
- string concatenation converted to f-strings
- a ton of improvements to unit tests, checking for types, and conversion possibilities, though most of them for
  `Bitvavo`, not for `Bitvavo.websocket`
- simplified a few functions; though I wrote tests for them to confirm behavior before changing them
- improved type hints for several functions - for example: replaced some `Any`'s with `Union[List[anydict], anydict]`;
  in other words: reduced the use of `Any`

### Removed

- the old non-documentation above each function (it usually started with `# options:`)

## v1.6.0 - 2021-12-29

Bugfix round! All found bugs in the original code should now be fixed.

### Changed

- fixed ["Negative sleep time length"](https://github.com/bitvavo/python-bitvavo-api/pull/22)
- fixed ["API response error when calling depositAssets()"](https://github.com/bitvavo/python-bitvavo-api/pull/18)
- in `Bitvavo.candles()` renamed the `symbol` argument to `market`, because candles expects a market, and not a
  symbol... The only API break I've done so far, but it's super minor.

## v1.5.0 - 2021-12-29

### Added

- separate README for pypi; now I can keep that separate from the one on Github; they can share _some_ information, but
  don't need to share all
- guides on how to get started as either a users or a developer (who wants to work on this lib)
- test support for Python 3.7 - 3.10

### Changed

- dependencies are now loosened so users of this lib get more freedom to choose their versions

## v1.4.1 - 2021-12-29

### Changed

- nothing, I just need to push a new commit to Github so I can trigger a new publish

## v1.4.0 - 2021-12-29

### Changed

- set the `mypy` settings to something sane (as per some rando internet articles)
- `pre-commit` `flake8` support; this was initially disabled due to too a lack of sane settings
- reduced pyupgrade from `--py39-plus` to `--py38-plus`, due to `39` changing `Dict` to `dict` and `List` to `list`, but
  `mypy` not being able to handle those new types yet.
- added types to _all_ functions, methods and classes

## v1.3.3 - 2021-12-29

### Changed

- fix the workflow (hopefully) - if I did, then this is the last you'll see about that

## v1.3.2 - 2021-12-29

### Changed

- fix requirements; 1.3.1 is _broken_

## v1.3.1 - 2021-12-29

### Changed

- easy fix to enable publishing to PyPi: disable the `if` that checks for tags 😅

## v1.3.0 - 2021-12-28

### Changed

- when there's a version bump, Github should push to PyPi now (not only to https://test.pypi.org)

## v1.1.1 - 2021-12-28

### Changed

- improved description

## v1.1.0 - 2021-12-28

### Added

- a metric fuckton of tests to check if everything works as expected. said tests are a bit... rough, but it's better
  than nothing, as I already found two bugs that showed that the original code _did not work!_
- two fixtures: `bitvavo` and `websocket`, each used to test each category of methods (REST vs websockets)

### Changed

- renamed the `python_bitvavo_api` folder to `bitvavo_api_upgraded`
- replaced `websocket` lib with `websocket-client`; I picked the wrong lib, initially, due to a lack of requirements in
  the original repo
- the `*ToConsole` functions now use the logging library from Python, as the print statement raised an exception when it
  received a exception object, instead of a string message...... (the `+` symbol was sorta the culprit, but not really -
  the lack of tests was the true culprit)
- the `on_*` methods now have either an extra `self` or `ws` argument, needed to unfuck the websocket code

### Removed

...

## v1.0.2 - 2021-12-27

Everything from since NostraDavid started this project; version `1.0.0` and `1.0.1` did not have `bump2version` working
well yet, which is why they do not have separate entries

### Added

- autopublishing to pypi
- capability to use a `.env` file to hold `BITVAVO_APIKEY` and `BITVAVO_APISECRET` variables
- `setup.py`; it was missing as _someone_ added it to .gitignore
- `__init__.py` to turn the code into a package (for `setup.py`)
- `MANIFEST.in` to include certain files in the source distribution of the app (needed for tox)
- `scripts/bootstrap.sh` to get newbies up and running faster
- ton of tools (`pre-commit`, `tox`, `pytest`, `flake8`, etc; see `requirements/dev.txt` for more information)
- ton of settings (either in `tox.ini`, `pyproject.toml`, or in a dedicated file like `.pre-commit-config` or
  `.bumpversion.cfg`)
- stub test to `test_bitvavo.py` to make tox happy
- added `# type: ignore` in `bitvavo.py` to shush mypy

### Changed

- moved `python_bitvavo_api` into the `src` folders
- moved and renamed `src/python_bitvavo_api/testApi.py` to `tests/test_bitvavo.py` (for `pytest` compatibility)

### Removed

- Nothing yet; I kept code changes to a minimum, until I got `bump2version` working with a `CHANGELOG.md` to prevent
  changing things without noting it down.
