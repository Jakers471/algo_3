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
│   │   ├── instruments.py per-symbol tick/point value (read from audit)
│   │   ├── session.py     UTC + RTH hours (09:30-16:00 ET)
│   │   └── backtest.py    slippage, backtest window, gap/hold policy
│   ├── audit/           read the data-truth facts from DATA_AUDIT.json
│   │   └── reader.py       front door: specs, handling flags, data end
│   ├── logging/         the logging job: dials + the setup that applies them
│   │   ├── settings.py     log level + destination (the value of the dial)
│   │   └── setup.py        setup_logging(): how/where logs render
│   ├── core/            shared infrastructure used everywhere
│   │   └── console.py       ANSI color codes + paint() (no emoji, ever)
│   └── broker/          all ProjectX API access (plumbing) — the engine
│       ├── client.py      connection + auth; exposes post() for reuse
│       ├── accounts.py    search accounts, pick a tradable one
│       ├── contracts.py   search contracts, resolve a symbol to its id
│       └── history.py     fetch OHLCV bars for a contract
├── (top level, not code): .env, logs/, data/, projectX_API/
```

## Dependency graph (who imports who)

Arrows point from a file to what it imports. Deeper = more foundational.

```
broker.accounts  ─► broker.client
broker.contracts ─► broker.client
broker.history   ─► broker.client
broker.client    ─► requests            (external HTTP library)

logging.setup    ─► logging.settings    (reads the dial value)
                 └► core.console         (color codes)

config.__init__  ─► dotenv               (loads .env once)
config.broker    ─► os                   (reads secrets from env)

config.instruments ─► audit.reader       (tick/point values from the audit)
config.backtest    ─► audit.reader       (data_end + handling flags)
audit.reader       ─► DATA_AUDIT.json     (the data's own rules, read once)
```

### What this shows at a glance

- **`broker.client` is the hub.** Every other broker module depends on it for the connection and its shared `post()`. Written once, reused everywhere — never duplicated.
- **`core/` is the foundation.** `console` is depended on but depends on almost nothing itself. That's why it lives in `core/`. (The logging *setup* moved to its own `logging/` folder, sitting next to the `settings` dials it applies — one folder for the whole logging job.)
- **`audit/` is the deepest data-truth leaf.** `audit.reader` reads `DATA_AUDIT.json` once and hands the facts out; `config.instruments` and `config.backtest` read *from* it. Data-truth flows out of `audit/`, never in.
- **`config/` is (almost) a leaf.** Everyone reads dials from it; it depends on nothing but `os`/`dotenv` — except the two sections that draw data-truth from `audit.reader`. Settings flow *out*, never in.

## Entry points (the doors you can run)

**None yet.** `broker/` is a verified, reusable engine (auth → account → contract → bars) awaiting its first command. When a workflow is built (e.g. live trading, health check), it adds a thin `cli/` door here, wired into `commands.bat`.

## Note on API history depth

`retrieveBars` is **per-contract**. The active NQ contract (`CON.F.US.ENQ.U26`) only serves ~1 month of history (verified: back to ~2026-06-07). The API is a *recent-data* source, not deep history — multi-year continuous history is the NT8 Parquet in `data/`. Building a continuous series would require stitching successive quarterly contracts.

## Backtest data reference

The historical NQ/ES Parquet in `data/` is audited in `DATA_AUDIT.md` (human) and `DATA_AUDIT.json` (machine). `audit/reader.py` is the code that reads that JSON; `config/instruments.py`, `config/session.py`, and `config/backtest.py` turn its fixed facts (contract specs, timezone, `handling` flags) into the dials the backtest engine runs on. Data is clean; the flags (gap-awareness, back-adjustment, fills/slippage, staleness) are what the engine must honor — they now live as config, seeded from the audit.

## Not built yet (planned shape)

These get created — with their config section alongside — when the area is actually built: `cli/` (interface doors), `broker/orders.py`, `broker/positions.py`, `strategy/`, `backtest/` (the engine that reads `config/backtest.py`), `risk/`, `config/live.py`, `config/risk.py`.
