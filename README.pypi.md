# Bitvavo API (upgraded)

A **typed, tested, and enhanced** Python wrapper for the Bitvavo cryptocurrency exchange API. This is an "upgraded" fork of the official Bitvavo SDK with comprehensive improvements and modern architecture.

## Why Choose This Over the Official SDK?

### Modern Architecture

- **Two interfaces**: Legacy `Bitvavo` class for backward compatibility + new `BitvavoClient` for modern development
- **Modular design**: Clean separation between public/private APIs, transport, and authentication
- **Type safety**: Complete type annotations with generics and precise return types

### Quality & Reliability

- **Comprehensive test suite** (found and fixed multiple bugs in the original)
- **Enhanced error handling** with detailed validation messages
- **Rate limiting** with automatic throttling and multi-key support
- **Up-to-date API compliance** including MiCA regulatory requirements

### Data Format Flexibility

- **Multiple output formats**: Raw dictionaries, validated Pydantic models, or DataFrames
- **Unified dataframe support** via Narwhals (pandas, polars, cuDF, modin, PyArrow, Dask, DuckDB, Ibis, PySpark)
- **Result types** for functional error handling

### Developer Experience

- **Modern Python support** (3.9+, dropped EOL versions)
- **Configuration via environment variables** or Pydantic settings
- **Enhanced documentation** with comprehensive examples
- **Developer-friendly tooling** (ruff, mypy, pre-commit hooks)

## Quick Start

```bash
pip install bitvavo_api_upgraded
```

### Two Ways to Use This Package

#### Option 1: New BitvavoClient (Recommended)

Modern, modular interface with clean architecture:

```python
from bitvavo_client import BitvavoClient, BitvavoSettings

# Auto-load from .env file
settings = BitvavoSettings()
client = BitvavoClient(**settings.model_dump())

# Access public endpoints (no auth needed)
time_result = client.public.time()
markets_result = client.public.markets()

# Access private endpoints (auth required)
balance_result = client.private.balance()
orders_result = client.private.orders('BTC-EUR')
```

#### Option 2: Legacy Bitvavo (Backward Compatibility)

Drop-in replacement for the official SDK:

```python
from bitvavo_api_upgraded import Bitvavo

bitvavo = Bitvavo({'APIKEY': 'your-key', 'APISECRET': 'your-secret'})
balance = bitvavo.balance({})
```

## Breaking Changes in v2.0.0

**MiCA Compliance Update**: All trading operations now require an `operatorId` parameter:

```python
# Before (v1.17.x and earlier)
bitvavo.placeOrder(market="BTC-EUR", side="buy", orderType="limit", body={...})

# After (v2.0.0+)
bitvavo.placeOrder(market="BTC-EUR", side="buy", orderType="limit", body={...}, operatorId=12345)
```

**New MiCA reporting endpoints**:

- `reportTrades()` - Generate trade reports for regulatory compliance
- `reportBook()` - Generate order book reports
- `accountHistory()` - Detailed account transaction history## Compatibility Promise

Version `1.*` maintains compatibility with the original API, with these improvements:

- **Fixed**: `Bitvavo.candles()` - renamed `symbol` → `market` parameter (was a bug)
- **Fixed**: `Bitvavo.book()` - same `symbol` → `market` fix
- **Removed**: Internal `rateLimitThread` class (cleaner implementation)

## Configuration Options

### Environment Variables

Create a `.env` file in your project root:

```env
# API authentication
BITVAVO_API_KEY=your-api-key-here
BITVAVO_API_SECRET=your-api-secret-here

# Client behavior
BITVAVO_PREFER_KEYLESS=true          # Use keyless for public endpoints
BITVAVO_DEFAULT_RATE_LIMIT=1000      # Rate limit per key
BITVAVO_DEBUGGING=false              # Enable debug logging

# Legacy format (still supported)
BITVAVO_APIKEY=your-api-key-here
BITVAVO_APISECRET=your-api-secret-here
```

### Usage Examples

#### New BitvavoClient

```python
from bitvavo_client import BitvavoClient, BitvavoSettings

# Auto-load from .env
client = BitvavoClient()

# Custom settings
settings = BitvavoSettings(
    api_key="your-key",
    api_secret="your-secret",
    prefer_keyless=True
)
client = BitvavoClient(settings)
```

#### Legacy Bitvavo

```python
from bitvavo_api_upgraded import Bitvavo, BitvavoSettings

# Auto-load from .env file
settings = BitvavoSettings()
bitvavo = Bitvavo(settings.model_dump())

# Or manual configuration with multiple keys
bitvavo = Bitvavo({
    'APIKEYS': [
        {'key': 'your-key-1', 'secret': 'your-secret-1'},
        {'key': 'your-key-2', 'secret': 'your-secret-2'}
    ],
    'PREFER_KEYLESS': True
})

# Or keyless for public endpoints only
bitvavo = Bitvavo({'PREFER_KEYLESS': True})
```

## Multi-Key & Keyless API Access

### Multiple API Keys

Distribute API calls across multiple keys for better rate limit management:

```python
from bitvavo_api_upgraded import Bitvavo

# Multiple keys automatically balance load
bitvavo = Bitvavo({
    'APIKEYS': [
        {'key': 'key1', 'secret': 'secret1'},
        {'key': 'key2', 'secret': 'secret2'},
        {'key': 'key3', 'secret': 'secret3'}
    ]
})

# API automatically switches between keys when rate limits are reached
balance = bitvavo.balance({})  # Uses least-used key
orders = bitvavo.getOrders('BTC-EUR', {})  # May use different key
```

### Keyless (Public) Access

Access public endpoints without authentication:

```python
from bitvavo_api_upgraded import Bitvavo

# No API keys needed for public data
bitvavo = Bitvavo({'PREFER_KEYLESS': True})

# These work without authentication
markets = bitvavo.markets({})
ticker = bitvavo.ticker24h({'market': 'BTC-EUR'})
trades = bitvavo.publicTrades('BTC-EUR', {})
book = bitvavo.book('BTC-EUR', {})
```

## WebSocket Support

Real-time data streaming with automatic reconnection:

```python
def handle_ticker(data):
    print(f"BTC-EUR: {data['price']}")

ws = bitvavo.newWebsocket()
ws.subscriptionTicker("BTC-EUR", handle_ticker)
```

## Advanced Features

- **Rate Limiting**: Automatic throttling with `getRemainingLimit()`
- **Error Handling**: Comprehensive error responses with proper typing
- **Lag Compensation**: Client-server time difference calculation
- **Ban Management**: Automatic detection and recovery from temporary bans
- **Type Safety**: Full type hints for better IDE support and fewer runtime errors

## Migration from Official SDK

### Option 1: Quick Migration (Legacy Interface)

1. **Install**: `pip install bitvavo_api_upgraded`
2. **Update imports**: `from bitvavo_api_upgraded import Bitvavo`
3. **Add operatorId**: Include in all trading operations (placeOrder, updateOrder, cancelOrder)
4. **Enjoy**: Better error handling, type hints, and reliability!

### Option 2: Modern Architecture (New Interface)

For new projects or when refactoring:

```python
# Old
from python_bitvavo_api.bitvavo import Bitvavo
bitvavo = Bitvavo({'APIKEY': 'key', 'APISECRET': 'secret'})

# New
from bitvavo_client import BitvavoClient, BitvavoSettings
client = BitvavoClient(BitvavoSettings(api_key='key', api_secret='secret'))
```

### Breaking Changes in v2.0.0

**MiCA Compliance**: All trading operations now require an `operatorId` parameter:

```python
# Before (v1.17.x and earlier)
bitvavo.placeOrder(market="BTC-EUR", side="buy", orderType="limit", body={...})

# After (v2.0.0+)
bitvavo.placeOrder(market="BTC-EUR", side="buy", orderType="limit", body={...}, operatorId=12345)
```

## Links & Resources

- [Official Bitvavo API Documentation](https://docs.bitvavo.com/)
- [Trading Rules & Terminology](https://bitvavo.com/en/trading-rules) (helpful for understanding crypto trading concepts)
- [GitHub Repository](https://github.com/Thaumatorium/bitvavo-api-upgraded) (source code, issues, contributions)
- [PyPI Package](https://pypi.org/project/bitvavo-api-upgraded/) (installation and version history)
- [Changelog](https://github.com/Thaumatorium/bitvavo-api-upgraded/blob/master/CHANGELOG.md) (detailed version history)

---

_This package is not affiliated with Bitvavo. It's an independent enhancement of their Python SDK._
