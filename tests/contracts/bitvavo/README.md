# Private Bitvavo API contracts

The tests pin the Exchange contract reviewed through **2026-08-07**. The official
OpenAPI `info.version` still says **2.10.0**, despite later numbered releases
such as **v2.12.0** and dated releases in 2026. Keep this metadata version separate
from the reviewed contract version. The HTTP API base path remains `/v2`.
The manifest records the source URL, upstream SHA-256, local schema checksum,
reviewed release URLs and rate-limit weights.

The versioned JSON snapshot preserves the request and response constraints for
the 16 operations currently exposed by `PrivateAPI`. Descriptions, examples
and other documentation annotations were removed. Response descriptions remain
as empty strings because OpenAPI requires that field. The snapshot and synthetic
responses are independent of the SDK's Pydantic models.

## Running the tests

Run `devenv shell -- just test` or `just check` inside the development shell.
These contract tests always use synthetic credentials and the reserved
`bitvavo.invalid` hostname. They send Niquests' actual prepared requests to an
in-process Connexion application. No TCP server or exchange connection is used.
The provider verifies HMAC signatures over the actual path, query and body,
checks access windows, and validates requests and responses against OpenAPI.
Socket connections and DNS lookups are blocked by the test suite.

The tests cover raw, Pydantic and Polars output, order creation/read/update/cancel,
mass cancellation, withdrawals, pagination, authentication errors, parameter
validation and documented rate-limit costs. Order matching, actual fills,
settlement, custody and bank transfers are not simulated. Newly published API
operations that the SDK does not expose are outside this fixture's scope.
Minimal order acknowledgements stay raw JSON when `responseRequired=false`,
including when a full order model was selected.

## Reviewed schema corrections

`bitvavo_stub.load_specification` applies these explicit corrections to a copy;
the pinned source snapshot stays unchanged:

| Location | Correction and reason |
| --- | --- |
| POST/PUT `/order`, GET `/deposit`, GET `/depositHistory` | The object alternatives overlap because their properties are optional. Use `anyOf` so a valid response is not rejected for matching both branches. Property validation stays active. |
| GET `/ordersOpen`, `/depositHistory`, `/withdrawalHistory` | The published schema describes an individual item. Wrap that item in an array to preserve the SDK's established list-response contract. This is a documented compatibility assumption to review when upstream clarifies the schema. |
| DELETE `/order` | Make `orderId` optional because `clientOrderId` is an alternative identifier. The fixture still requires an existing matching order. |
| GET `/trades` | Remove the stale `tradeId` query parameter, as specified in the 2025-06-30 release. The SDK's old input alias is tested to send `tradeIdTo` instead. |

The suite deliberately corrupts a response to prove that Connexion rejects it.
These corrections do not disable response validation.

## Keeping the contract current

`just contract-check` fetches only the official documentation schema and release
feed. It fails if the upstream schema bytes change or a newer Exchange API
release appears. Feed timestamps order both numbered and dated releases.
Sneak previews and releases of other Bitvavo APIs are ignored.
The same check runs weekly and on manual dispatch in `bitvavo-contract.yml`.
Normal tests remain offline.

On failure, review the changed OpenAPI and release notes before updating the
versioned snapshot, synthetic responses and manifest. Update or remove the
schema corrections when upstream fixes them. Add a regression for meaningful
behavior changes and run `just check`. Never refresh the pins automatically to
make a failing compatibility check pass. Prose-only schema edits also require a
review because the upstream checksum covers the complete download.

Sources:

- [Official OpenAPI](https://docs.bitvavo.com/api-specs/exchange-rest-api.yaml)
- [Exchange releases](https://docs.bitvavo.com/releases/)
- [Authentication and signing](https://docs.bitvavo.com/docs/rest-api/introduction/)
- [Error codes](https://docs.bitvavo.com/docs/errors/)
- [2025-05-08 order errors](https://docs.bitvavo.com/releases/2025-05-08-exchange/)
- [2025-06-30 operator IDs and removed parameters](https://docs.bitvavo.com/releases/2025-06-30-exchange/)
- [2025-09-28 tick size](https://docs.bitvavo.com/releases/2025-09-28-exchange/)
- [v2.12.0, the same 2025-09-28 release](https://docs.bitvavo.com/releases/v2.12.0/)
- [2026-05-19 rate limits](https://docs.bitvavo.com/releases/2026-05-19-exchange/)
- [2026-08-07 trade operator IDs](https://docs.bitvavo.com/releases/2026-08-07-exchange/)
