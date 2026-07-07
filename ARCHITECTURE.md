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
│   │   ├── console.py       ANSI color codes + paint() (no emoji, ever)
│   │   └── progress.py      in-place ANSI progress bar for long loops
│   ├── data/           load the NT8 Parquet store into clean bars — engine
│   │   ├── loader.py      read a symbol/TF Parquet -> raw UTC OHLCV (I/O)
│   │   └── prepare.py     window + gap-mark + zero-vol policy (logic)
│   ├── indicators/     shared raw math (pure) — strategies compose these
│   │   ├── volume_profile.py  volume-per-row + value area (POC/VAH/VAL core)
│   │   ├── grade.py           OHLCV window -> regime (efficiency/acceptance -> state)
│   │   └── sessions.py        group bars into Asia/London/NY session instances
│   ├── strategy/       bars -> bracket order intents (signals)
│   │   ├── bracket.py     Direction + Bracket (entry stop + SL/TP as absolute levels)
│   │   ├── breakout.py    Donchian long/short starter (entry_signals) + params
│   │   └── registry.py    name -> strategy class (build one from a run config)
│   ├── backtest/       resolve brackets against bars -> fills, PnL, stats
│   │   ├── fills.py       pure fill model (slippage, gaps, adverse-first flag)
│   │   ├── engine.py      the bar loop; emits Trades (MAE/MFE/ETD, hold policy)
│   │   └── runspec.py     load a JSON run config; label a run (replayable)
│   ├── optimize/       search a param grid over one window, rank by objective
│   │   ├── grid.py        expand a param grid into every combo
│   │   ├── objective.py   score Stats by a named objective (min-trades guard)
│   │   └── sweep.py       backtest each combo on a window; rank best-first
│   ├── walkforward/    optimize IS -> test OOS -> stitch (honest validation)
│   │   ├── folds.py       generate IS/OOS window folds (rolling/anchored)
│   │   ├── wfaspec.py     the JSON walk-forward run config (replayable)
│   │   └── engine.py      per fold: sweep IS, run best on OOS, stitch + WFE
│   ├── reporting/      Trades -> saved, shareable run artifacts
│   │   ├── stats.py       All/Long/Short metrics (+ json/text writers)
│   │   ├── trades.py      trade list -> CSV (machine) + aligned text (human)
│   │   ├── equity.py      equity + drawdown image (matplotlib PNG)
│   │   ├── folds.py       walk-forward per-fold table -> CSV + text
│   │   ├── console.py     terminal All/Long/Short + fold summaries (color)
│   │   └── run.py         bundle a backtest or WFA into a labeled run/ folder
│   ├── broker/         all ProjectX API access (plumbing) — the engine
│   │   ├── client.py      connection + auth; exposes post() for reuse
│   │   ├── accounts.py    search accounts, pick a tradable one
│   │   ├── contracts.py   search contracts, resolve a symbol to its id
│   │   └── history.py     fetch OHLCV bars for a contract
│   └── cli/            thin doors: parse input, call an engine, format out
│       ├── data.py        load & summarize prepared bars (python -m src.cli.data)
│       ├── backtest.py    run a backtest from a config; save a labeled run
│       └── walkforward.py run a walk-forward from a config; save a labeled run
├── run_configs/        JSON run recipes (tracked) — strategy + params + data
├── runs/               labeled run outputs (git-ignored): trades, summary, equity.png
├── tests/              pytest suite (dev tooling, not product code)
│   └── test_fills.py     pins the fill model's honest assumptions
├── conftest.py         puts repo root on sys.path so tests import `src`
├── (top level, not code): .env, logs/, data/, projectX_API/
```

## Dependency graph (who imports who)

Arrows point from a file to what it imports. Deeper = more foundational.

```
broker.accounts  ─► broker.client
broker.contracts ─► broker.client
broker.history   ─► broker.client
broker.client    ─► requests            (external HTTP library)

data.prepare     ─► data.loader         (raw bars to clean)
                 └► config.backtest      (window + zero-vol policy)
data.loader      ─► pandas               (reads the Parquet store)

cli.data         ─► data.prepare         (the bars engine it drives)
                 ├► logging.setup         (configure logging at startup)
                 └► core.console          (color the summary)

indicators.grade    ─► indicators.volume_profile   (profile + value area)
indicators.sessions ─► config.session              (session windows + tz)

strategy.breakout ─► strategy.bracket   (emits Bracket order intents)
strategy.registry ─► strategy.breakout   (name -> class)
(a GRADE-based strategy will import indicators.grade to build its signals)
backtest.engine   ─► backtest.fills      (resolve fills against a bar)
                  ├► strategy.bracket     (the order intent it consumes)
                  ├► config.backtest      (slippage, commission, hold policy)
                  └► config.instruments   (tick/point value for PnL)
backtest.runspec  ─► json                 (load the run config; a manifest replays)

reporting.stats   ─► backtest.engine      (the Trade type)
reporting.trades  ─► backtest.engine      (Trade -> CSV/text)
reporting.equity  ─► matplotlib, backtest.engine   (Trade -> PNG)
reporting.folds   ─► (walk-forward fold results -> CSV/text)
reporting.console ─► reporting.stats, core.console (terminal summaries)
reporting.run     ─► reporting.{trades,stats,equity,folds}, backtest.runspec  (labeled run)

optimize.sweep    ─► optimize.{grid,objective}, backtest.engine, reporting.stats, strategy.registry
walkforward.engine ─► walkforward.folds, optimize.{sweep,objective}, backtest.engine,
                      reporting.stats, strategy.registry, config.backtest

cli.backtest      ─► data.prepare, strategy.registry, backtest.{engine,runspec},
                     reporting.{stats,console,run}, core.progress
cli.walkforward   ─► data.prepare, walkforward.{engine,folds,wfaspec},
                     reporting.{stats,console,run}, core.progress

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

- **`python -m src.cli.data [SYMBOL] [TIMEFRAME]`** — load prepared bars (default `NQ 5m`) and print a summary (rows, range, session-gap count). Wired into `commands.bat` → Data.
- **`python -m src.cli.backtest run_configs/<name>.json`** — run a backtest from a JSON run config with a progress bar, print the All/Long/Short summary, and save a **labeled run** to `runs/<timestamp>_<strategy>_<params>/` (trades.csv/txt, summary.json/txt, equity.png, run.json manifest). The manifest replays as a config. A run is always defined by a config. Wired into `commands.bat` → Backtest.
- **`python -m src.cli.walkforward run_configs/<name>.json`** — run a walk-forward analysis: for each fold, optimize the param grid in-sample and test the winner out-of-sample, then stitch the OOS trades. Prints the per-fold table + stitched-OOS summary + walk-forward efficiency; saves a labeled run (adds `folds.csv/txt`, `wfa.json`). Judge on the stitched OOS, never the in-sample optimization. Wired into `commands.bat` → Backtest.

`broker/` is a verified, reusable engine (auth → account → contract → bars) still awaiting its own command (e.g. live trading, health check); when built it adds another thin `cli/` door here, wired into `commands.bat`.

## Note on API history depth

`retrieveBars` is **per-contract**. The active NQ contract (`CON.F.US.ENQ.U26`) only serves ~1 month of history (verified: back to ~2026-06-07). The API is a *recent-data* source, not deep history — multi-year continuous history is the NT8 Parquet in `data/`. Building a continuous series would require stitching successive quarterly contracts.

## Backtest data reference

The historical NQ/ES Parquet in `data/` is audited in `DATA_AUDIT.md` (human) and `DATA_AUDIT.json` (machine). `audit/reader.py` is the code that reads that JSON; `config/instruments.py`, `config/session.py`, and `config/backtest.py` turn its fixed facts (contract specs, timezone, `handling` flags) into the dials the backtest engine runs on. Data is clean; the flags (gap-awareness, back-adjustment, fills/slippage, staleness) are what the engine must honor — they now live as config, seeded from the audit.

## Not built yet (planned shape)

These get created — with their config section alongside — when the area is actually built: `broker/orders.py`, `broker/positions.py`, `risk/` (sizing/limits, reads `config/risk.py`), `execution/` (live loop, reads `config/live.py`), `config/live.py`, `config/risk.py`. (`data/`, `strategy/`, `backtest/`, and `cli/` now exist.)
