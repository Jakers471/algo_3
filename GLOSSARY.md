# GLOSSARY.md — the domain map

**What the trading words mean, and where each one lives in the project.** This is the *domain map*: the concepts the program is *about* (accounts, contracts, bars…). For how the *code* is wired, see `ARCHITECTURE.md` — the *code map*.

The key idea: **every domain concept is a thread** running through the project — config says *which/how much*, a code file *does it*, an API endpoint *serves it*, and a doc *explains it*. Each entry below traces that thread.

Keep this file current: when a new domain concept enters the project, add its definition and its thread in the same commit.

---

## account
A trading account at the broker (e.g. a TopstepX evaluation or funded account). Has an `id`, `name`, `balance`, and a `canTrade` flag. You pick one account to trade with.

| Layer | Where |
|-------|-------|
| Code | `src/broker/accounts.py` (`search_accounts`, `select_tradable`) |
| API | `POST /api/Account/search` |
| Docs | `projectX_API/account/trades/search_account.md` |

## contract
A specific tradeable futures instrument — *this is a trading term, not a code term*. A future literally *is* a contract (an agreement to buy/sell at a future date). Example: the E-mini Nasdaq-100 (`symbolId` `F.US.ENQ`), whose current tradeable contract has an id like `CON.F.US.ENQ.Z24`. Distinct from the Micro (`F.US.MNQ`).

| Layer | Where |
|-------|-------|
| Config | `src/config/data.py` (`DEFAULT_SYMBOL_SEARCH`, `DEFAULT_SYMBOL_ID`) |
| Code | `src/broker/contracts.py` (`search_contracts`, `resolve_symbol`) |
| API | `POST /api/Contract/search`, `/api/Contract/searchById`, `/api/Contract/available` |
| Docs | `projectX_API/account/market_data/search_contracts.md` |

## bar (OHLCV)
One candle of price history for a contract over a time unit: **o**pen, **h**igh, **l**ow, **c**lose, **v**olume, plus a timestamp **t**. Units: 1=second, 2=minute, 3=hour, 4=day, 5=week, 6=month. Max 20,000 bars per request.

| Layer | Where |
|-------|-------|
| Config | `src/config/data.py` (`DEFAULT_LOOKBACK_DAYS`, `DEFAULT_BAR_LIMIT`) |
| Code | `src/broker/history.py` (`retrieve_bars`, `UNIT_*` constants) |
| API | `POST /api/History/retrieveBars` |
| Docs | `projectX_API/account/market_data/retrieve_bars.md` |

## token / session (auth)
The JWT bearer token proving who you are. Obtained by logging in with username + API key; refreshed before it expires (~24h). Sent on every request as `Authorization: Bearer <token>`.

| Layer | Where |
|-------|-------|
| Config | `src/config/broker.py` (`USERNAME`, `API_KEY`, `TOKEN` — from `.env`) |
| Code | `src/broker/client.py` (`ProjectXClient.connect`, `_login`, `_validate`) |
| API | `POST /api/Auth/loginKey`, `POST /api/Auth/validate` |
| Docs | `projectX_API/account/getting_started/authenticate_api_key.md` |

---

## Planned concepts (not built yet)

Defined here as the target; their threads get filled in when the area is built.

## order
An instruction to buy or sell a contract (market, limit, stop…). Not yet implemented.

| Layer | Where (planned) |
|-------|-----------------|
| Code | `src/broker/orders.py` |
| API | `POST /api/Order/place`, `/api/Order/modify`, `/api/Order/cancel` |
| Docs | `projectX_API/account/orders/place_order.md` |

## position
An open holding in a contract (long/short, size, entry). Result of filled orders. Not yet implemented.

| Layer | Where (planned) |
|-------|-----------------|
| Code | `src/broker/positions.py` |
| API | `POST /api/Position/searchOpen`, `/api/Position/closeContract` |
| Docs | `projectX_API/account/market_data/positions/search_positions.md` |
