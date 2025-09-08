# Bitvavo API (upgraded)

A **typed, tested, and enhanced** Python wrapper for the Bitvavo cryptocurrency exchange API. This is an "upgraded" fork of the official Bitvavo SDK with comprehensive type hints, unit tests, modern architecture, and improved developer experience.

## Quick Start

```bash
pip install bitvavo_api_upgraded
```

### Basic Usage

```python
# Option 1: Original Bitvavo interface (legacy)
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'APIKEY': 'your-key', 'APISECRET': 'your-secret'})
balance = bitvavo.balance({})

# Option 2: New modular BitvavoClient interface (recommended)
from bitvavo_client import BitvavoClient, BitvavoSettings

client = BitvavoClient()
result = client.public.time()  # No authentication needed
result = client.private.balance()  # Authentication required
```

### Optional Dataframe Support

This package supports multiple dataframe libraries via [Narwhals](https://narwhals-dev.github.io/narwhals/), providing a unified interface across:

- **pandas** - The most popular Python data analysis library
- **polars** - Fast, memory-efficient DataFrames in Rust
- **cuDF** - GPU-accelerated DataFrames (NVIDIA RAPIDS)
- **modin** - Distributed pandas on Ray/Dask
- **PyArrow** - In-memory columnar data format
- **Dask** - Parallel computing with task scheduling
- **DuckDB** - In-process analytical database
- **Ibis** - Portable analytics across backends
- **PySpark** - Distributed data processing
- **PySpark Connect** - Client for remote Spark clusters
- **SQLFrame** - SQL-like operations on DataFrames

Install with your preferred dataframe library:

```bash
# Basic installation (dict output only)
pip install bitvavo_api_upgraded

# With pandas support
pip install bitvavo_api_upgraded[pandas]

# With polars support
pip install bitvavo_api_upgraded[polars]

# With multiple libraries
pip install bitvavo_api_upgraded[pandas,polars,pyarrow]

# With GPU acceleration (cuDF)
pip install bitvavo_api_upgraded[cudf]

# With distributed computing (Dask)
pip install bitvavo_api_upgraded[dask]

# Note: polars-gpu support will be available in a future release
```

Scroll down for detailed usage examples and configuration instructions.

## What Makes This "Upgraded"?

This wrapper improves upon the official Bitvavo SDK with:

### Modern Architecture

- **Modular design**: Clean separation between public/private APIs, transport, and authentication
- **Two interfaces**: Legacy `Bitvavo` class for backward compatibility + new `BitvavoClient` for modern development
- **Dependency injection**: Testable, maintainable, and extensible codebase
- **Type safety**: Comprehensive type annotations with generics and precise return types

### Quality & Reliability

- **Comprehensive test suite** (found and fixed multiple bugs in the original)
- **100% type coverage** with mypy strict mode
- **Enhanced error handling** with detailed validation messages
- **Rate limiting** with automatic throttling and multi-key support

### Data Format Flexibility

- **Unified dataframe support** via Narwhals (pandas, polars, cuDF, modin, PyArrow, Dask, DuckDB, Ibis, PySpark, SQLFrame)
- **Pydantic models** for validated, structured data
- **Raw dictionary access** for backward compatibility
- **Result types** for functional error handling

### Enhanced Performance

- **Multi-key support** for better rate limiting and load distribution
- **Keyless access** for public endpoints (doesn't count against your API limits)
- **Connection pooling** and retry logic
- **Async-ready architecture** (async support coming in future release)

### Developer Experience

- **Modern Python support** (3.9+, dropped EOL versions)
- **Configuration via environment variables** or Pydantic settings
- **Detailed changelog** tracking all changes and improvements
- **Enhanced documentation** with examples and clear usage patterns
- **Developer-friendly tooling** (ruff, mypy, pre-commit hooks)

## Features

### Full API Coverage

- All REST endpoints (public and private)
- Multiple API key support with automatic load balancing
- Keyless access for public endpoints without authentication
- Comprehensive dataframe support via Narwhals (pandas, polars, cuDF, modin, PyArrow, Dask, DuckDB, Ibis, PySpark, and more)
- WebSocket support with reconnection logic
- Rate limiting with automatic throttling
- MiCA compliance reporting endpoints

### Developer Experience

- Type hints for better IDE support
- Comprehensive error handling
- Detailed logging with `structlog`
- Configuration via `.env` files
- Extensive test coverage

### Production Ready

- Automatic rate limit management
- Multi-key failover support
- Connection retry logic
- Proper error responses
- Memory efficient WebSocket handling

## Configuration

### Environment Variables

Create a `.env` file in your project root:

```env
# API authentication
BITVAVO_API_KEY=your-api-key-here
BITVAVO_API_SECRET=your-api-secret-here

# Multi-key support (JSON array as string)
# BITVAVO_API_KEYS='[{"key": "key1", "secret": "secret1"}, {"key": "key2", "secret": "secret2"}]'

# Client behavior
BITVAVO_PREFER_KEYLESS=true          # Use keyless for public endpoints
BITVAVO_DEFAULT_RATE_LIMIT=1000      # Rate limit per key
BITVAVO_RATE_LIMIT_BUFFER=50         # Buffer to avoid hitting limits
BITVAVO_DEBUGGING=false              # Enable debug logging

# API endpoints (usually not needed to change)
BITVAVO_REST_URL=https://api.bitvavo.com/v2
BITVAVO_WS_URL=wss://ws.bitvavo.com/v2/
```

### Usage Examples

#### New BitvavoClient (Recommended)

```python
from bitvavo_client import BitvavoClient, BitvavoSettings

# Option 1: Auto-load from .env file
client = BitvavoClient()

# Option 2: Custom settings
settings = BitvavoSettings(
    api_key="your-key",
    api_secret="your-secret",
    prefer_keyless=True,
    debugging=True
)
client = BitvavoClient(settings)

# Option 3: Manual settings override
client = BitvavoClient(BitvavoSettings(default_rate_limit=750))

# Access public endpoints (no auth needed)
time_result = client.public.time()
markets_result = client.public.markets()

# Access private endpoints (auth required)
balance_result = client.private.balance()
account_result = client.private.account()
```

#### Legacy Bitvavo Class (Backward Compatibility)

```python
from bitvavo_api_upgraded import Bitvavo, BitvavoSettings

# Option 1: Manual configuration
bitvavo = Bitvavo({
    'APIKEY': 'your-key',
    'APISECRET': 'your-secret'
})

# Option 2: Auto-load from .env
settings = BitvavoSettings()
bitvavo = Bitvavo(settings.model_dump())

# Option 3: Multiple API keys
bitvavo = Bitvavo({
    'APIKEYS': [
        {'key': 'key1', 'secret': 'secret1'},
        {'key': 'key2', 'secret': 'secret2'}
    ]
})

# Option 4: Keyless (public endpoints only)
bitvavo = Bitvavo({'PREFER_KEYLESS': True})
```

## Data Format Flexibility

The new BitvavoClient supports multiple output formats to match your workflow:

### Model Preferences

```python
from bitvavo_client import BitvavoClient
from bitvavo_client.core.model_preferences import ModelPreference

# Option 1: Raw dictionaries (default, backward compatible)
client = BitvavoClient(preferred_model=ModelPreference.RAW)
result = client.public.time()  # Returns: {"time": 1609459200000}

# Option 2: Validated Pydantic models
client = BitvavoClient(preferred_model=ModelPreference.PYDANTIC)
result = client.public.time()  # Returns: ServerTime(time=1609459200000)

# Option 3: DataFrame format (pandas, polars, etc.)
client = BitvavoClient(preferred_model=ModelPreference.POLARS)
result = client.public.markets()  # Returns: polars.DataFrame with market data
```

### Per-Request Format Override

```python
# Set a default preference but override per request
client = BitvavoClient(preferred_model=ModelPreference.RAW)

# Get raw dict (uses default)
raw_data = client.public.markets()

# Override to get Polars DataFrame for this request
import polars as pl
from bitvavo_client.core.model_preferences import ModelPreference
df_data = client.public.markets(model=ModelPreference.POLARS)

# Override to get Pydantic model
from bitvavo_client.core.public_models import Markets
validated_data = client.public.markets(model=Markets)
```

### Result Types for Error Handling

```python
from returns.result import Success, Failure

# Use result types for functional error handling
result = client.public.time()

if isinstance(result, Success):
    print(f"Server time: {result.unwrap()}")
elif isinstance(result, Failure):
    print(f"Error: {result.failure()}")

# Or use match-case (Python 3.10+)
match result:
    case Success(value):
        print(f"Success: {value}")
    case Failure(error):
        print(f"Error: {error}")
```

## WebSocket Usage

```python
from bitvavo_api_upgraded import Bitvavo

def handle_ticker(data):
    print(f"Ticker update: {data}")

def handle_error(error):
    print(f"Error: {error}")

# Initialize WebSocket
bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})
ws = bitvavo.newWebsocket()
ws.setErrorCallback(handle_error)

# Subscribe to ticker updates
ws.subscriptionTicker("BTC-EUR", handle_ticker)

# Keep connection alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ws.closeSocket()
```

## Multi-Key & Keyless Examples

### Multiple API Keys for Rate Limiting

```python
from bitvavo_api_upgraded import Bitvavo

# Configure multiple API keys
bitvavo = Bitvavo({
    'APIKEYS': [
        {'key': 'key1', 'secret': 'secret1'},
        {'key': 'key2', 'secret': 'secret2'},
        {'key': 'key3', 'secret': 'secret3'}
    ]
})

# API automatically balances load across keys
balance = bitvavo.balance({})  # Uses least-used key
orders = bitvavo.getOrders('BTC-EUR', {})  # May use different key
trades = bitvavo.getTrades('BTC-EUR', {})  # Automatic failover if rate limit reached
```

### Keyless Access (Public Endpoints)

```python
from bitvavo_api_upgraded import Bitvavo

# No API keys needed for public data
bitvavo = Bitvavo({'PREFER_KEYLESS': True})

# These work without authentication and don't count against your rate limits
markets = bitvavo.markets({})
ticker = bitvavo.ticker24h({'market': 'BTC-EUR'})
trades = bitvavo.publicTrades('BTC-EUR', {})
book = bitvavo.book('BTC-EUR', {})
candles = bitvavo.candles('BTC-EUR', '1h', {})

# Private endpoints will still require authentication
# account = bitvavo.account()  # This would fail without API keys
```

### Hybrid Configuration

```python
# Combine keyless preference with API keys for optimal performance
bitvavo = Bitvavo({
    'APIKEYS': [
        {'key': 'key1', 'secret': 'secret1'},
        {'key': 'key2', 'secret': 'secret2'}
    ],
    'PREFER_KEYLESS': True  # Use keyless for public endpoints, API keys for private
})

# Public calls use keyless (no rate limit impact)
markets = bitvavo.markets({})

# Private calls use API keys with load balancing
balance = bitvavo.balance({})
```

## API Examples

### Public Endpoints (No Authentication Required)

#### New BitvavoClient Interface

```python
from bitvavo_client import BitvavoClient

client = BitvavoClient()

# Get server time
time_result = client.public.time()

# Get all markets
markets_result = client.public.markets()

# Get specific market
btc_market = client.public.markets(market='BTC-EUR')

# Get order book
book_result = client.public.book('BTC-EUR')

# Get recent trades
trades_result = client.public.trades('BTC-EUR')

# Get 24h ticker
ticker_result = client.public.ticker_24h(market='BTC-EUR')

# Get candlestick data
candles_result = client.public.candles('BTC-EUR', '1h')
```

#### Legacy Bitvavo Interface

```python
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'PREFER_KEYLESS': True})  # For public endpoints

# Get server time
time_resp = bitvavo.time()

# Get all markets
markets = bitvavo.markets({})

# Get specific market
btc_market = bitvavo.markets({'market': 'BTC-EUR'})

# Get order book
book = bitvavo.book('BTC-EUR', {})

# Get recent trades
trades = bitvavo.publicTrades('BTC-EUR', {})

# Get 24h ticker
ticker = bitvavo.ticker24h({'market': 'BTC-EUR'})
```

### Private Endpoints (Authentication Required)

#### New BitvavoClient Interface

```python
from bitvavo_client import BitvavoClient, BitvavoSettings

# Configure with API credentials
settings = BitvavoSettings(api_key="your-key", api_secret="your-secret")
client = BitvavoClient(settings)

# Get account info
account_result = client.private.account()

# Get balance
balance_result = client.private.balance()

# Place order
order_result = client.private.place_order(
    market="BTC-EUR",
    side="buy",
    order_type="limit",
    amount="0.01",
    price="45000"
)

# Get order history
orders_result = client.private.orders('BTC-EUR')

# Cancel order
cancel_result = client.private.cancel_order(
    market="BTC-EUR",
    order_id="order-id-here"
)

# Get trades
trades_result = client.private.trades('BTC-EUR')
```

#### Legacy Bitvavo Interface

```python
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'APIKEY': 'your-key', 'APISECRET': 'your-secret'})

# Get account info
account = bitvavo.account()

# Get balance
balance = bitvavo.balance({})

# Place order (requires operatorId for MiCA compliance)
order = bitvavo.placeOrder(
    market="BTC-EUR",
    side="buy",
    orderType="limit",
    body={"amount": "0.01", "price": "45000"},
    operatorId=12345
)

# Get order history
orders = bitvavo.getOrders('BTC-EUR', {})

# Cancel order
cancel_result = bitvavo.cancelOrder(
    market="BTC-EUR",
    orderId="order-id-here",
    operatorId=12345
)
```

### MiCA Compliance Features

```python
# Generate trade report
trade_report = bitvavo.reportTrades(
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

### Dataframe Usage

The library supports multiple dataframe formats for tabular data like market data, asset information, and candlestick data:

```python
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})

# Get markets as different dataframe types
markets_dict = bitvavo.markets({}, output_format='dict')         # Default dict format
markets_pandas = bitvavo.markets({}, output_format='pandas')     # Pandas DataFrame
markets_polars = bitvavo.markets({}, output_format='polars')     # Polars DataFrame
markets_pyarrow = bitvavo.markets({}, output_format='pyarrow')   # PyArrow Table

# Get assets information as dataframes
assets_cudf = bitvavo.assets(
    {},
    output_format='cudf'  # GPU-accelerated with cuDF
)

# Get candlestick data with distributed processing
candles_dask = bitvavo.candles(
    'BTC-EUR',
    '1h',
    {'limit': 100},
    output_format='dask'  # Distributed with Dask
)

# Get public trades with analytical databases
trades_duckdb = bitvavo.publicTrades(
    'BTC-EUR',
    {'limit': 1000},
    output_format='duckdb'  # DuckDB relation
)

# Account balance with PySpark for big data processing
balance_spark = bitvavo.balance(
    {},
    output_format='pyspark'  # PySpark DataFrame
)
```

### Working with Different Libraries

```python
# Pandas example - most common
import pandas as pd
df = bitvavo.markets({}, output_format='pandas')
print(df.describe())
df.to_csv('markets.csv')

# Polars example - faster for large datasets
import polars as pl
df = bitvavo.candles('BTC-EUR', '1h', {'limit': 1000}, output_format='polars')
result = df.filter(pl.col('close') > 50000).select(['timestamp', 'close'])

# DuckDB example - analytical queries
import duckdb
rel = bitvavo.publicTrades('BTC-EUR', {'limit': 10000}, output_format='duckdb')
high_volume_trades = duckdb.query("SELECT * FROM rel WHERE amount > 1.0")

# PyArrow example - columnar data
import pyarrow as pa
table = bitvavo.assets({}, output_format='pyarrow')
df = table.to_pandas()  # Convert to pandas when needed
```

## Error Handling

```python
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})

response = bitvavo.placeOrder(
    market="BTC-EUR",
    side="buy",
    orderType="limit",
    body={"amount": "0.01", "price": "45000"},
    operatorId=12345
)

# Check for errors
if isinstance(response, dict) and 'errorCode' in response:
    print(f"Error {response['errorCode']}: {response['error']}")
else:
    print(f"Order placed successfully: {response['orderId']}")
```

## Rate Limiting

```python
# Check remaining rate limit
remaining = bitvavo.getRemainingLimit()
print(f"Remaining API calls: {remaining}")

# The library automatically handles rate limiting
# But you can check limits before making calls
if remaining > 10:
    # Safe to make API calls
    response = bitvavo.balance({})

# With multiple API keys, rate limits are distributed
bitvavo_multi = Bitvavo({
    'APIKEYS': [
        {'key': 'key1', 'secret': 'secret1'},
        {'key': 'key2', 'secret': 'secret2'}
    ]
})

# Each key gets its own rate limit pool
# Automatic failover when one key hits limits
for i in range(2000):  # Would exceed single key limit
    markets = bitvavo_multi.markets({})  # Automatically switches keys

# Keyless calls don't count against authenticated rate limits
bitvavo_keyless = Bitvavo({'PREFER_KEYLESS': True})
markets = bitvavo_keyless.markets({})  # Uses public rate limit pool
```

## Development & Contributing

````shell
echo "install development requirements"
uv sync
echo "run tox, a program that creates separate environments for different python versions, for testing purposes (among other things)"
uv run tox
## Development & Contributing

### Setup Development Environment

```shell
# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/Thaumatorium/bitvavo-api-upgraded.git
cd bitvavo-api-upgraded

# Install dependencies
uv sync

# Run tests across Python versions
uv run tox

# Run tests for current Python version
uv run pytest

# Type checking
uv run mypy src/

# Linting and formatting
uv run ruff check
uv run ruff format
````

### Project Structure

```text
src/
├── bitvavo_api_upgraded/           # Legacy interface (backward compatibility)
│   ├── __init__.py                 # Main exports
│   ├── bitvavo.py                  # Original monolithic API class
│   ├── settings.py                 # Pydantic settings
│   ├── helper_funcs.py             # Utility functions
│   └── type_aliases.py             # Type definitions
└── bitvavo_client/                 # Modern modular interface
    ├── __init__.py                 # New client exports
    ├── facade.py                   # Main BitvavoClient class
    ├── core/                       # Core functionality
    │   ├── settings.py             # Settings management
    │   ├── models.py               # Pydantic data models
    │   ├── validation_helpers.py   # Enhanced error handling
    │   └── types.py                # Type definitions
    ├── endpoints/                  # API endpoint handlers
    │   ├── public.py               # Public API endpoints
    │   ├── private.py              # Private API endpoints
    │   └── common.py               # Shared endpoint utilities
    ├── transport/                  # HTTP transport layer
    │   └── http.py                 # HTTP client with connection pooling
    ├── auth/                       # Authentication & authorization
    │   ├── signing.py              # Request signing
    │   └── rate_limit.py           # Rate limiting management
    ├── adapters/                   # External integrations
    │   └── returns_adapter.py      # Result type adapters
    ├── schemas/                    # DataFrame schemas
    │   ├── public_schemas.py       # Public endpoint schemas
    │   └── private_schemas.py      # Private endpoint schemas
    └── df/                         # DataFrame conversion
        └── convert.py              # Narwhals-based converters

tests/                              # Comprehensive test suite
├── bitvavo_api_upgraded/           # Legacy interface tests
└── bitvavo_client/                 # Modern interface tests
    ├── core/                       # Core functionality tests
    ├── endpoints/                  # Endpoint tests
    ├── transport/                  # Transport layer tests
    ├── auth/                       # Authentication tests
    ├── adapters/                   # Adapter tests
    └── df/                         # DataFrame tests

docs/                               # Documentation
```

### Semantic Versioning

This project follows [semantic versioning](https://semver.org/):

1. **MAJOR** version for incompatible API changes
2. **MINOR** version for backwards-compatible functionality additions
3. **PATCH** version for backwards-compatible bug fixes

## Type Annotations

This package includes a `py.typed` file to enable type checking. Reference: [Don't forget py.typed for your typed Python package](https://blog.whtsky.me/tech/2021/dont-forget-py.typed-for-your-typed-python-package/)

## Migration & Architecture Options

This package provides **two interfaces** to suit different use cases:

### 1. Legacy Bitvavo Class (Backward Compatibility)

For existing users migrating from the official SDK:

```python
from bitvavo_api_upgraded import Bitvavo

# Drop-in replacement for python_bitvavo_api.bitvavo
bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})
balance = bitvavo.balance({})
```

### 2. New BitvavoClient (Modern Architecture)

For new projects or those wanting better architecture:

```python
from bitvavo_client import BitvavoClient, BitvavoSettings

# Modern, typed, modular interface
client = BitvavoClient()
result = client.public.time()
result = client.private.balance()
```

### Migration from Official SDK

#### Key Changes

- **Import**: `from bitvavo_api_upgraded import Bitvavo` (instead of `from python_bitvavo_api.bitvavo import Bitvavo`)
- **Breaking**: Trading operations require `operatorId` parameter
- **Enhanced**: Better error handling and type safety
- **New**: Modern `BitvavoClient` interface available
- **New**: Multiple API key support for rate limiting
- **New**: Keyless access for public endpoints
- **New**: Comprehensive dataframe support
- **New**: Configuration via `.env` files

#### Migration Steps

1. **Update import statements**

   ```python
   # Old
   from python_bitvavo_api.bitvavo import Bitvavo

   # New (legacy interface)
   from bitvavo_api_upgraded import Bitvavo

   # New (modern interface)
   from bitvavo_client import BitvavoClient
   ```

2. **Add operatorId to trading operations**

   ```python
   # Add operatorId parameter to placeOrder, cancelOrder, etc.
   order = bitvavo.placeOrder("BTC-EUR", "buy", "limit", {...}, operatorId=12345)
   ```

3. **Optional: Migrate to modern interface**

   ```python
   # Legacy style
   bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})

   # Modern style
   client = BitvavoClient(BitvavoSettings(api_key='key', api_secret='secret'))
   ```

4. **Optional: Use new features**

   ```python
   # Multi-key support
   bitvavo = Bitvavo({'APIKEYS': [{'key': 'k1', 'secret': 's1'}, {'key': 'k2', 'secret': 's2'}]})

   # Keyless for public endpoints
   bitvavo = Bitvavo({'PREFER_KEYLESS': True})

   # DataFrame support
   markets_df = bitvavo.markets({}, output_format='pandas')
   ```

### Choosing an Interface

| Feature                    | Legacy `Bitvavo`       | Modern `BitvavoClient`     |
| -------------------------- | ---------------------- | -------------------------- |
| **Backward compatibility** | ✅ Drop-in replacement | ❌ New interface           |
| **Type safety**            | ✅ Typed responses     | ✅ Full generics support   |
| **Error handling**         | ✅ Enhanced errors     | ✅ Result types + enhanced |
| **Modular design**         | ❌ Monolithic          | ✅ Separated concerns      |
| **Testing**                | ✅ Testable            | ✅ Highly testable         |
| **DataFrame support**      | ✅ Via output_format   | ✅ Via model preferences   |
| **Result types**           | ❌ Exceptions only     | ✅ Success/Failure pattern |
| **WebSocket support**      | ✅ Full support        | 🚧 Coming soon             |

**Recommendation**:

- Use **Legacy `Bitvavo`** for quick migrations and WebSocket usage
- Use **Modern `BitvavoClient`** for new projects requiring clean architecture

---

## Original Bitvavo SDK Documentation

The following is preserved from the original Bitvavo SDK for reference.

Crypto starts with Bitvavo. You use Bitvavo SDK for Python to buy, sell, and
store over 200 digital assets on Bitvavo from inside your app.

To trade and execute your advanced trading strategies, Bitvavo SDK for Python is
a wrapper that enables you to easily call every endpoint in [Bitvavo
API](https://docs.bitvavo.com/).

- [Prerequisites](#prerequisites) - what you need to start developing with
  Bitvavo SDK for Python
- [Get started](#get-started) - rapidly create an app and start trading with
  Bitvavo
- [About the SDK](#about-the-sdk) - general information about Bitvavo SDK for
  Python
- [API reference](https://docs.bitvavo.com/) - information on the specifics of
  every parameter

This page shows you how to use Bitvavo SDK for Python with WebSockets. For REST,
see the [REST readme](docs/rest.md).

## Prerequisites

To start programming with Bitvavo SDK for Python you need:

- [Python3](https://www.python.org/downloads/) installed on your development
  environment

  If you are working on macOS, ensure that you have installed SSH certificates:

  ```terminal
  open /Applications/Python\ 3.12/Install\ Certificates.command
  open /Applications/Python\ 3.12/Update\ Shell\ Profile.command
  ```

- A Python app. Use your favorite IDE, or run from the command line
- An [API key and
  secret](https://support.bitvavo.com/hc/en-us/articles/4405059841809)
  associated with your Bitvavo account

  You control the actions your app can do using the rights you assign to the API
  key. Possible rights are:

  - **View**: retrieve information about your balance, account, deposit and
    withdrawals
  - **Trade**: place, update, view and cancel orders
  - **Withdraw**: withdraw funds

    Best practice is to not grant this privilege, withdrawals using the API do
    not require 2FA and e-mail confirmation.

## Get started

Want to quickly make a trading app? Here you go:

1. **Install Bitvavo SDK for Python**

   In your Python app, add [Bitvavo SDK for
   Python](https://github.com/bitvavo/python-bitvavo-api) from
   [pypi.org](https://pypi.org/project/python-bitvavo-api/):

   ```shell
   python -m pip install python_bitvavo_api
   ```

   If you installed from `test.pypi.com`, update the requests library: `pip
install --upgrade  requests`.

1. **Create a simple Bitvavo implementation**

   Add the following code to a new file in your app:

   ```python
   from python_bitvavo_api.bitvavo import Bitvavo
   import json
   import time

   # Use this class to connect to Bitvavo and make your first calls.
   # Add trading strategies to implement your business logic.
   class BitvavoImplementation:
       api_key = "<Replace with your your API key from Bitvavo Dashboard>"
       api_secret = "<Replace with your API secret from Bitvavo Dashboard>"
       bitvavo_engine = None
       bitvavo_socket = None

       # Connect securely to Bitvavo, create the WebSocket and error callbacks.
       def __init__(self):
           self.bitvavo_engine = Bitvavo({
               'APIKEY': self.api_key,
               'APISECRET': self.api_secret
           })
           self.bitvavo_socket = self.bitvavo_engine.newWebsocket()
           self.bitvavo_socket.setErrorCallback(self.error_callback)

       # Handle errors.
       def error_callback(self, error):
           print("Add your error message.")
           #print("Errors:", json.dumps(error, indent=2))

       # Retrieve the data you need from Bitvavo in order to implement your
       # trading logic. Use multiple workflows to return data to your
       # callbacks.
       def a_trading_strategy(self):
           self.bitvavo_socket.ticker24h({}, self.a_trading_strategy_callback)

       # In your app you analyse data returned by the trading strategy, then make
       # calls to Bitvavo to respond to market conditions.
       def a_trading_strategy_callback(self, response):
           # Iterate through the markets
           for market in response:

               match market["market"]:
                  case "ZRX-EUR":
                       print("Eureka, the latest bid for ZRX-EUR is: ", market["bid"] )
                       # Implement calculations for your trading logic.
                       # If they are positive, place an order: For example:
                       # self.bitvavo_socket.placeOrder("ZRX-EUR",
                       #                               'buy',
                       #                               'limit',
                       #                               { 'amount': '1', 'price': '00001' },
                       #                               self.order_placed_callback)
                  case "a different market":
                       print("do something else")
                  case _:
                       print("Not this one: ", market["market"])



       def order_placed_callback(self, response):
           # The order return parameters explain the quote and the fees for this trade.
           print("Order placed:", json.dumps(response, indent=2))
           # Add your business logic.


       # Sockets are fast, but asynchronous. Keep the socket open while you are
       # trading.
       def wait_and_close(self):
           # Bitvavo uses a weight based rate limiting system. Your app is limited to 1000 weight points per IP or
           # API key per minute. The rate weighting for each endpoint is supplied in Bitvavo API documentation.
           # This call returns the amount of points left. If you make more requests than permitted by the weight limit,
           # your IP or API key is banned.
           limit = self.bitvavo_engine.getRemainingLimit()
           try:
               while (limit > 0):
                   time.sleep(0.5)
                   limit = self.bitvavo_engine.getRemainingLimit()
           except KeyboardInterrupt:
               self.bitvavo_socket.closeSocket()


   # Shall I re-explain main? Naaaaaaaaaa.
   if __name__ == '__main__':
       bvavo = BitvavoImplementation()
       bvavo.a_trading_strategy()
       bvavo.wait_and_close()
   ```

1. **Add security information**

   You must supply your security information to trade on Bitvavo and see your
   account information using the authenticate methods. Replace the values of
   `api_key` and `api_secret` with your credentials from [Bitvavo
   Dashboard](https://account.bitvavo.com/user/api).

   You can retrieve public information such as available markets, assets and
   current market without supplying your key and secret. However,
   unauthenticated calls have lower rate limits based on your IP address, and
   your account is blocked for longer if you exceed your limit.

1. **Run your app**

   - Command line warriors: `python3 <filename>`.
   - IDE heroes: press the big green button.

Your app connects to Bitvavo and returns a list the latest trade price for each
market. You use this data to implement your trading logic.

## About the SDK

This section explains global concepts about Bitvavo SDK for Python.

### Rate limit

Bitvavo uses a weight based rate limiting system. Your app is limited to 1000
weight points per IP or API key per minute. When you make a call to Bitvavo API,
your remaining weight points are returned in the header of each REST request.

Websocket methods do not return your returning weight points, you track your
remaining weight points with a call to:

```python
limit = bitvavo.getRemainingLimit()
```

If you make more requests than permitted by the weight limit, your IP or API key
is banned.

The rate weighting for each endpoint is supplied in the [Bitvavo API
documentation](https://docs.bitvavo.com/).

### Requests

For all methods, required parameters are passed as separate values, optional
parameters are passed as a dictionary. Return parameters are in dictionary
format: `response['<key>'] = '<value>'`. However, as a limit order requires more
information than a market order, some optional parameters are required when you
place an order.

### Security

You must set your API key and secret for authenticated endpoints, public
endpoints do not require authentication.
