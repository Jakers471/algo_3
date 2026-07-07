# ProjectX / TopstepX Gateway API — Docs

Reference markdown for the **ProjectX (TopstepX) Gateway API**. All endpoints are `POST`, JSON in / JSON out, over `https://api.topstepx.com`.

## Connection

- **API base:** `https://api.topstepx.com`
- **User Hub (realtime):** `https://rtc.topstepx.com/hubs/user`
- **Market Hub (realtime):** `https://rtc.topstepx.com/hubs/market`
- **Auth:** JWT bearer token. Get one via `loginKey`, refresh via `validate`. Send as `Authorization: Bearer <token>`.
- **Token life:** ~24h; re-validate before expiry to get a rolling `newToken`.

## Rate limits

| Endpoint | Limit |
|----------|-------|
| `POST /api/History/retrieveBars` | 50 req / 30s |
| All other endpoints | 200 req / 60s |

Exceeding → `HTTP 429`.

## Endpoints

### Getting started (`account/getting_started/`)
| Endpoint | Purpose | Doc |
|----------|---------|-----|
| `POST /api/Auth/loginKey` | Authenticate with username + API key → session token | `authenticate_api_key.md` |
| `POST /api/Auth/validate` | Validate/refresh token → `newToken` | `validate_session.md` |
| — | Connection URLs | `connection_urls.md` |
| — | Rate limits | `rate_limits.md` |
| — | Placing your first order (walkthrough) | `placing_first_order.md` |

### Accounts & trades (`account/trades/`)
| Endpoint | Purpose | Doc |
|----------|---------|-----|
| `POST /api/Account/search` | List/search accounts | `search_account.md` |
| `POST /api/Trade/search` | Search executed trades | `search_trades.md` |

### Market data (`account/market_data/`)
| Endpoint | Purpose | Doc |
|----------|---------|-----|
| `POST /api/Contract/available` | List available contracts | `list_available_contracts.md` |
| `POST /api/Contract/search` | Search contracts | `search_contracts.md` |
| `POST /api/Contract/searchById` | Look up a contract by ID | `search_contract_by_id.md` |
| `POST /api/History/retrieveBars` | Historical OHLCV bars | `retrieve_bars.md` |
| — | Realtime data overview (SignalR hubs) | `realtime_updates/realtime_data_overview.md` |

### Positions (`account/market_data/positions/`)
| Endpoint | Purpose | Doc |
|----------|---------|-----|
| `POST /api/Position/searchOpen` | Search open positions | `search_positions.md` |
| `POST /api/Position/closeContract` | Close a position | `close_positions.md` |
| `POST /api/Position/partialCloseContract` | Partially close a position | `partially_close_positions.md` |

### Orders (`account/orders/`)
| Endpoint | Purpose | Doc |
|----------|---------|-----|
| `POST /api/Order/place` | Place an order | `place_order.md` |
| `POST /api/Order/modify` | Modify an order | `modify_order.md` |
| `POST /api/Order/cancel` | Cancel an order | `cancel_order.md` |
| `POST /api/Order/search` | Search orders | `search_orders.md` |
| `POST /api/Order/searchOpen` | Search open orders | `search_open_orders.md` |

## Other files

- `account/brokers.json` — broker/firm reference data.
