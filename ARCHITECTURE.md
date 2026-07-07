# ARCHITECTURE.md — the code map

**How the code is wired.** This is the *code map*: the folder tree and who-imports-who. For what the trading words mean (account, contract, bar…), see the `projectX_API/` docs.

Keep this file current: whenever a module is added, moved, renamed, or its imports change, update this map in the same commit.

## Folder tree

```
algo_3/
├── src/
│   ├── config/          settings, sectioned by area (dials you edit)
│   │   ├── __init__.py    loads .env once (single secret-load point)
│   │   ├── broker.py      API endpoints; credentials from .env
│   │   ├── data.py        default symbol, lookback, bar limits
│   │   └── logging.py     log level + destination (the value of the dial)
│   ├── core/            shared infrastructure used everywhere
│   │   ├── console.py       ANSI color codes + paint() (no emoji, ever)
│   │   └── logging_config.py  setup_logging(): how/where logs render
│   └── broker/          all ProjectX API access (plumbing) — the engine
│       ├── client.py      connection + auth; exposes post() for reuse
│       ├── accounts.py    search accounts, pick a tradable one
│       ├── contracts.py   search contracts, resolve a symbol to its id
│       └── history.py     fetch OHLCV bars for a contract
├── config/data (top level, not code): .env, logs/, data/, projectX_API/
```

## Dependency graph (who imports who)

Arrows point from a file to what it imports. Deeper = more foundational.

```
broker.accounts  ─► broker.client
broker.contracts ─► broker.client
broker.history   ─► broker.client
broker.client    ─► requests            (external HTTP library)

core.logging_config ─► config.logging   (reads the dial value)
                    └► core.console      (color codes)

config.__init__  ─► dotenv               (loads .env once)
config.broker    ─► os                   (reads secrets from env)
```

### What this shows at a glance

- **`broker.client` is the hub.** Every other broker module depends on it for the connection and its shared `post()`. Written once, reused everywhere — never duplicated.
- **`core/` is the foundation.** `console` and `logging_config` are depended on but depend on almost nothing themselves (only stdlib + config). That's why they live in `core/`.
- **`config/` is a leaf.** Everyone reads from it; it depends on nothing but `os`/`dotenv`. Settings flow *out*, never in.

## Entry points (the doors you can run)

**None yet.** `broker/` is a verified, reusable engine (auth → account → contract → bars) awaiting its first command. When a workflow is built (e.g. live trading, health check), it adds a thin `cli/` door here, wired into `commands.bat`.

## Note on API history depth

`retrieveBars` is **per-contract**. The active NQ contract (`CON.F.US.ENQ.U26`) only serves ~1 month of history (verified: back to ~2026-06-07). The API is a *recent-data* source, not deep history — multi-year continuous history is the NT8 Parquet in `data/`. Building a continuous series would require stitching successive quarterly contracts.

## Backtest data reference

The historical NQ/ES Parquet in `data/` is audited in `DATA_AUDIT.md` (human) and `DATA_AUDIT.json` (machine — the backtest engine reads its `handling` flags). Data is clean; the flags (gap-awareness, back-adjustment, fills/slippage, staleness) are what the engine must honor.

## Not built yet (planned shape)

These get created — with their config section alongside — when the area is actually built: `cli/` (interface doors), `broker/orders.py`, `broker/positions.py`, `strategy/`, `backtest/`, `risk/`, `config/backtest.py`, `config/live.py`, `config/risk.py`.
