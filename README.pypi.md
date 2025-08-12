# Bitvavo API (upgraded)

A **typed, tested, and enhanced** Python wrapper for the Bitvavo cryptocurrency exchange API. This is an "upgraded" fork of the official Bitvavo SDK with comprehensive improvements.

## Why Choose This Over the Official SDK?

- 🎯 **Complete type annotations** for all functions and classes (better IDE
  support)
- 🧪 **Comprehensive test suite** (found and fixed 6+ bugs in the original
  untested code)
- 📋 **Detailed changelog** tracking all changes and improvements
- 🔄 **Up-to-date API compliance** including MiCA regulatory requirements
  (v2.0.0+)
- 🐍 **Modern Python support** (3.9+, dropped EOL versions)
- ⚡ **Enhanced reliability**:
  - Working `getRemainingLimit()` function
  - Automatic ban detection and waiting
  - Client-server lag compensation for stable API calls
  - Proper `ACCESSWINDOW` timeout handling
- 📚 **Better developer experience**:
  - Built-in documentation with examples
  - Fancy logging via `structlog` (including external libs)
  - Configuration via `.env` files with Pydantic validation

## Quick Start

```python
pip install bitvavo_api_upgraded
```

For code examples, look down below.

## 🚨 Breaking Changes in v2.0.0

It's somewhat minor:

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
- `accountHistory()` - Detailed account transaction history

## Compatibility Promise

Version `1.*` maintains compatibility with the original API, with these improvements:

- ✅ **Fixed**: `Bitvavo.candles()` - renamed `symbol` → `market` parameter (was a bug)
- ✅ **Fixed**: `Bitvavo.book()` - same `symbol` → `market` fix
- ✅ **Removed**: Internal `rateLimitThread` class (cleaner implementation)

## Configuration Options

Modern configuration via `.env` files (powered by Pydantic Settings):

```env
# Required: API credentials
BITVAVO_APIKEY=your-api-key-here
BITVAVO_APISECRET=your-api-secret-here

# Optional: Customize behavior
BITVAVO_API_UPGRADED_LOG_LEVEL=INFO                    # Logging level (DEBUG/INFO/WARNING/ERROR)
BITVAVO_API_UPGRADED_LOG_EXTERNAL_LEVEL=WARNING        # External libs logging level
BITVAVO_API_UPGRADED_LAG=50                            # Client-server lag compensation (ms)
BITVAVO_API_UPGRADED_RATE_LIMITING_BUFFER=25           # Rate limit buffer (increase if getting banned)
```

Then use in your code:

```python
from bitvavo_api_upgraded import Bitvavo, BitvavoSettings

# Auto-load from .env file
settings = BitvavoSettings()
bitvavo = Bitvavo(settings.model_dump())

# Or manual configuration
bitvavo = Bitvavo({
    'APIKEY': 'your-key',
    'APISECRET': 'your-secret'
})
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

1. **Install**: `pip install bitvavo_api_upgraded`
2. **Update imports**: `from bitvavo_api_upgraded import Bitvavo`
3. **Add operatorId**: Include in all trading operations (placeOrder, updateOrder, cancelOrder)
4. **Enjoy**: Better error handling, type hints, and reliability!

## Links & Resources

- 📚 [Official Bitvavo API Documentation](https://docs.bitvavo.com/)
- 📖 [Trading Rules & Terminology](https://bitvavo.com/en/trading-rules) (helpful for understanding crypto trading concepts)
- 🔧 [GitHub Repository](https://github.com/Thaumatorium/bitvavo-api-upgraded) (source code, issues, contributions)
- 📦 [PyPI Package](https://pypi.org/project/bitvavo-api-upgraded/) (installation and version history)
- 📋 [Changelog](https://github.com/Thaumatorium/bitvavo-api-upgraded/blob/master/CHANGELOG.md) (detailed version history)

---

*This package is not affiliated with Bitvavo. It's an independent enhancement of their Python SDK.*
