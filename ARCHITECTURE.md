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
│   │   ├── data.py        symbol, lookback, fetch timeframes, data dir
│   │   └── logging.py     log level + destination (the value of the dial)
│   ├── core/            shared infrastructure used everywhere
│   │   ├── console.py       ANSI color codes + paint() (no emoji, ever)
│   │   └── logging_config.py  setup_logging(): how/where logs render
│   ├── broker/          all ProjectX API access (plumbing)
│   │   ├── client.py      connection + auth; exposes post() for reuse
│   │   ├── accounts.py    search accounts, pick a tradable one
│   │   ├── contracts.py   search contracts, resolve a symbol to its id
│   │   └── history.py     fetch OHLCV bars; retrieve_history() pages back
│   ├── storage/         persist data to disk
│   │   └── csv_store.py    save bars -> data/<SYMBOL>_<TF>.csv
│   └── cli/             interface — thin doors that orchestrate
│       └── fetch.py       fetch all NQ history per timeframe → save CSV
├── config/data (top level, not code): .env, logs/, data/, projectX_API/
```

## Dependency graph (who imports who)

Arrows point from a file to what it imports. Deeper = more foundational.

```
cli/fetch.py                            ← the entry point / orchestrator
  ├─► broker.client (ProjectXClient)
  ├─► broker.contracts
  ├─► broker.history      (retrieve_history — pages back to earliest)
  ├─► storage.csv_store   (save each timeframe to CSV)
  ├─► config.broker       (endpoints, credentials)
  ├─► config.data         (symbol, timeframes, data dir)
  ├─► core.console        (colored output)
  └─► core.logging_config (setup_logging)

broker.accounts  ─► broker.client
broker.contracts ─► broker.client
broker.history   ─► broker.client
broker.client    ─► requests            (external HTTP library)

storage.csv_store   ─► pandas            (tidy CSV write)

core.logging_config ─► config.logging   (reads the dial value)
                    └► core.console      (color codes)

config.__init__  ─► dotenv               (loads .env once)
config.broker    ─► os                   (reads secrets from env)
```

### What this shows at a glance

- **`broker.client` is the hub.** Every other broker module depends on it for the connection and its shared `post()`. Written once, reused everywhere — never duplicated.
- **`core/` is the foundation.** `console` and `logging_config` are depended on but depend on almost nothing themselves (only stdlib + config). That's why they live in `core/`.
- **`cli/fetch.py` sits on top.** It imports the most and is imported by nothing — the classic shape of an entry point. It only orchestrates; it holds no trading logic.
- **`config/` is a leaf.** Everyone reads from it; it depends on nothing but `os`/`dotenv`. Settings flow *out*, never in.

## Entry points (the doors you can run)

| Run this | File | What it does |
|----------|------|--------------|
| `python -m src.cli.fetch` | `cli/fetch.py` | Fetch all available NQ history (every timeframe) → save `data/NQ_<TF>.csv` |

New workflows (backtest, live, health) will each add a door here. See `COMMANDS.md` for exact invocations.

## Note on API history depth

`retrieveBars` is **per-contract**. The active NQ contract (`CON.F.US.ENQ.U26`) only serves ~1 month of history (verified: back to ~2026-06-07). The API is a *recent-data* source, not deep history — multi-year continuous history is the NT8 Parquet in `data/`. Building a continuous series would require stitching successive quarterly contracts.

## Not built yet (planned shape)

These get created — with their config section alongside — when the area is actually built: `broker/orders.py`, `broker/positions.py`, `strategy/`, `backtest/`, `risk/`, `config/backtest.py`, `config/live.py`, `config/risk.py`.
