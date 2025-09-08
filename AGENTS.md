# Agents

This repository contains several "agents" (modular components) that work together to provide a comprehensive Bitvavo
cryptocurrency exchange API client. The architecture follows a modern, modular design with clear separation of concerns.

## Core API Agents

### 1. Legacy Bitvavo Agent

- **Name**: `Bitvavo` (Legacy API)
- **Description**: Original monolithic API client that maintains backward compatibility with the official Bitvavo SDK.
  Handles both REST and WebSocket operations in a single class with comprehensive method coverage.
- **Inputs**:
  - API credentials (dict with APIKEY/APISECRET)
  - Method parameters (dicts for various endpoints)
  - WebSocket callback functions
- **Outputs**:
  - REST methods: `dict | list` for success, `errordict` for API errors
  - WebSocket methods: Use callbacks for event handling
- **Config / Env vars**:
  - `BITVAVO_APIKEY` - API key for authentication
  - `BITVAVO_APISECRET` - API secret for signing
  - Pydantic settings via `BitvavoSettings` and `BitvavoApiUpgradedSettings`
- **Links to code**: [`src/bitvavo_api_upgraded/bitvavo.py`](src/bitvavo_api_upgraded/bitvavo.py)

### 2. Modern BitvavoClient Agent

- **Name**: `BitvavoClient` (Modern Facade)
- **Description**: New modular client facade that provides a clean, testable interface with dependency injection.
  Orchestrates public/private API endpoints, rate limiting, and HTTP transport.
- **Inputs**:
  - `BitvavoSettings` configuration object
  - Optional model preferences for response formatting
  - Optional default schemas for DataFrame conversion
- **Outputs**:
  - Structured responses via public/private API endpoints
  - Support for multiple output formats (dict, Pydantic models, DataFrames)
- **Config / Env vars**:
  - Via `BitvavoSettings` from `bitvavo_client.core.settings`
  - Environment variable loading with `.env` support
- **Links to code**: [`src/bitvavo_client/facade.py`](src/bitvavo_client/facade.py)

## API Endpoint Agents

### 3. Public API Agent

- **Name**: `PublicAPI`
- **Description**: Handles all public Bitvavo API endpoints that don't require authentication. Provides market data,
  ticker information, order books, trade history, and candlestick data.
- **Inputs**:
  - HTTP client instance
  - Optional model preferences and schemas
  - Endpoint-specific parameters (market symbols, intervals, limits)
- **Outputs**:
  - Market data, tickers, order books, trades, candlesticks
  - Support for dict, Pydantic models, and DataFrame outputs
- **Config / Env vars**:
  - Inherits from base HTTP client configuration
  - No authentication required (keyless access)
- **Links to code**: [`src/bitvavo_client/endpoints/public.py`](src/bitvavo_client/endpoints/public.py)

### 4. Private API Agent

- **Name**: `PrivateAPI`
- **Description**: Handles all private Bitvavo API endpoints requiring authentication. Manages account data, balances,
  orders, trades, deposits, withdrawals, and fees.
- **Inputs**:
  - Authenticated HTTP client instance
  - Optional model preferences and schemas
  - Endpoint-specific parameters (order details, withdrawal info, etc.)
- **Outputs**:
  - Account information, balances, order responses, trade history
  - Transaction and deposit/withdrawal data
- **Config / Env vars**:
  - Requires valid API credentials via HTTP client
  - Inherits authentication from transport layer
- **Links to code**: [`src/bitvavo_client/endpoints/private.py`](src/bitvavo_client/endpoints/private.py)

## Transport & Infrastructure Agents

### 5. HTTP Transport Agent

- **Name**: `HTTPClient`
- **Description**: HTTP client for Bitvavo REST API with rate limiting, authentication, and connection management.
  Handles request signing, rate limit enforcement, and response processing.
- **Inputs**:
  - `BitvavoSettings` configuration
  - `RateLimitManager` instance
  - API requests with method, URL, and parameters
- **Outputs**:
  - HTTP responses wrapped in Result types
  - Rate limit updates and error handling
- **Config / Env vars**:
  - API base URLs, timeouts, retry settings
  - Authentication keys and secrets
- **Links to code**: [`src/bitvavo_client/transport/http.py`](src/bitvavo_client/transport/http.py)

### 6. Rate Limit Manager Agent

- **Name**: `RateLimitManager`
- **Description**: Manages rate limiting for multiple API keys and keyless requests. Implements Bitvavo's weight-based
  rate limiting (1000 points/minute) with automatic throttling and multi-key support.
- **Inputs**:
  - Default rate limit values and buffer settings
  - Request weights and API key indices
  - Optional custom rate limit strategies
- **Outputs**:
  - Rate limit budget checks and enforcement
  - Automatic sleep/retry when limits exceeded
- **Config / Env vars**:
  - `default_rate_limit` - Initial rate limit value
  - `rate_limit_buffer` - Safety buffer before hitting limits
- **Links to code**: [`src/bitvavo_client/auth/rate_limit.py`](src/bitvavo_client/auth/rate_limit.py)

### 7. Authentication/Signing Agent

- **Name**: `AuthenticationAgent` (via signing functions)
- **Description**: Handles HMAC-SHA256 signature creation for authenticated Bitvavo API requests. Implements the
  required signature format with timestamp and body hashing.
- **Inputs**:
  - HTTP method, path, timestamp, body content
  - API secret for HMAC signing
- **Outputs**:
  - HMAC-SHA256 signatures for request authentication
  - Properly formatted authentication headers
- **Config / Env vars**:
  - API secret key for signature generation
- **Links to code**: [`src/bitvavo_client/auth/signing.py`](src/bitvavo_client/auth/signing.py)

## Data Processing Agents

### 8. Model Preference Agent

- **Name**: `ModelPreference` system
- **Description**: Handles response format preferences, allowing users to choose between raw dictionaries, validated
  Pydantic models, or structured DataFrames for API responses.
- **Inputs**:
  - User preference settings (dict, model, or dataframe)
  - Raw API response data
  - Optional schema definitions
- **Outputs**:
  - Formatted responses in requested format
  - Validated data structures with proper typing
- **Config / Env vars**:
  - Default model preferences in client configuration
- **Links to code**: [`src/bitvavo_client/core/model_preferences.py`](src/bitvavo_client/core/model_preferences.py)

### 9. DataFrame Conversion Agent

- **Name**: `DataFrameUtils`
- **Description**: Provides unified DataFrame support across multiple libraries (pandas, polars, cuDF, etc.) via
  Narwhals. Converts API responses to DataFrames with proper schemas and type handling.
- **Inputs**:
  - Raw API response data (lists of dicts)
  - Schema definitions for DataFrame conversion
  - Target DataFrame library preference
- **Outputs**:
  - DataFrames in requested format (pandas, polars, etc.)
  - Proper column types and schema validation
- **Config / Env vars**:
  - DataFrame library preferences
  - Default schemas for different endpoints
- **Links to code**:
  - [`src/bitvavo_api_upgraded/dataframe_utils.py`](src/bitvavo_api_upgraded/dataframe_utils.py)
  - [`src/bitvavo_client/df/convert.py`](src/bitvavo_client/df/convert.py)

### 10. Returns Adapter Agent

- **Name**: `ReturnsAdapter`
- **Description**: Provides functional error handling via `returns.result.Result` types, mapping HTTP responses and
  Bitvavo API errors to structured Result monads for clean error propagation.
- **Inputs**:
  - HTTP responses from API calls
  - Raw response data and status codes
- **Outputs**:
  - `Result[T, BitvavoError]` types for functional error handling
  - Structured error information with proper typing
- **Config / Env vars**:
  - Error mapping configuration
  - Result type preferences
- **Links to code**: [`src/bitvavo_client/adapters/returns_adapter.py`](src/bitvavo_client/adapters/returns_adapter.py)

## Schema & Validation Agents

### 11. Pydantic Models Agent

- **Name**: `PydanticModels` (Public/Private)
- **Description**: Provides validated data models for all API endpoints using Pydantic v2. Ensures type safety, data
  validation, and structured responses with proper field typing.
- **Inputs**:
  - Raw API response dictionaries
  - Validation rules and field constraints
- **Outputs**:
  - Validated Pydantic model instances
  - Type-safe data structures with IDE support
- **Config / Env vars**:
  - Model validation settings
  - Field alias and constraint configurations
- **Links to code**:
  - [`src/bitvavo_client/core/public_models.py`](src/bitvavo_client/core/public_models.py)
  - [`src/bitvavo_client/core/private_models.py`](src/bitvavo_client/core/private_models.py)

### 12. Schema Definition Agent

- **Name**: `SchemaAgent`
- **Description**: Defines DataFrame schemas for consistent data structure across different endpoints. Provides default
  schemas for candlestick data, trade history, order books, and other API responses.
- **Inputs**:
  - API endpoint identifiers
  - Data type requirements and constraints
- **Outputs**:
  - Schema definitions for DataFrame conversion
  - Type mappings and field specifications
- **Config / Env vars**:
  - Default schema configurations per endpoint
- **Links to code**:
  - [`src/bitvavo_client/schemas/public_schemas.py`](src/bitvavo_client/schemas/public_schemas.py)
  - [`src/bitvavo_client/schemas/private_schemas.py`](src/bitvavo_client/schemas/private_schemas.py)

## Configuration & Settings Agents

### 13. Settings Management Agent

- **Name**: `SettingsAgent`
- **Description**: Manages configuration via Pydantic Settings with environment variable loading, .env file support, and
  validation. Handles both legacy and modern client configurations.
- **Inputs**:
  - Environment variables
  - .env files
  - Direct configuration objects
- **Outputs**:
  - Validated settings instances
  - Configuration for all client components
- **Config / Env vars**:
  - `BITVAVO_APIKEY`, `BITVAVO_APISECRET`
  - `BITVAVO_API_URL`, `BITVAVO_WS_URL`
  - Rate limiting and timeout configurations
- **Links to code**:
  - [`src/bitvavo_api_upgraded/settings.py`](src/bitvavo_api_upgraded/settings.py)
  - [`src/bitvavo_client/core/settings.py`](src/bitvavo_client/core/settings.py)

## WebSocket Agents (Legacy)

### 14. WebSocket Facade Agent

- **Name**: `WebSocketAppFacade`
- **Description**: WebSocket client for real-time market data with automatic reconnection, local order book maintenance,
  and event-driven callbacks. Part of the legacy Bitvavo class.
- **Inputs**:
  - WebSocket subscription parameters
  - Callback functions for different event types
  - Connection and reconnection settings
- **Outputs**:
  - Real-time market data events
  - Maintained local order books
  - Connection status updates
- **Config / Env vars**:
  - WebSocket URL and connection settings
  - Reconnection intervals and retry limits
- **Links to code**: [`src/bitvavo_api_upgraded/bitvavo.py`](src/bitvavo_api_upgraded/bitvavo.py) (nested class)

---

## Agent Interaction Flow

1. **Entry Points**: Users interact via either `Bitvavo` (legacy) or `BitvavoClient` (modern)
2. **Request Flow**: Client → HTTP Transport → Rate Limiting → Authentication → API Endpoints
3. **Response Flow**: API Response → Model Preference → DataFrame/Pydantic/Dict → User
4. **Configuration**: Settings Agent provides configuration to all other agents
5. **Error Handling**: Returns Adapter provides functional error handling across the stack

The modular design allows for easy testing, extension, and maintenance while providing multiple interfaces for different
use cases and preferences.
