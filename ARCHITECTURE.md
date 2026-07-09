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
│   │   ├── backtest.py    slippage, backtest window, gap/hold policy
│   │   ├── chart.py       chart server host/port, bar cache, replay dials
│   │   ├── replay.py      session idle timeout, subscriber queue, speeds
│   │   ├── live.py        contract id, which market streams, capture dir
│   │   └── indicators/    one module per indicator, named for its id
│   │       └── sessions.py  enable + band colors for the sessions indicator
│   ├── audit/           read the data-truth facts from DATA_AUDIT.json
│   │   └── reader.py       front door: specs, handling flags, data end
│   ├── logging/         the logging job: dials + the setup that applies them
│   │   ├── settings.py     log level + destination (the value of the dial)
│   │   └── setup.py        setup_logging(): how/where logs render
│   ├── core/            shared infrastructure used everywhere
│   │   ├── console.py       ANSI color codes + paint() (no emoji, ever)
│   │   └── progress.py      in-place ANSI progress bar for long loops
│   ├── events/         the market event vocabulary (bars, later ticks/quotes)
│   │   └── types.py       BarClose: a completed bar, stamped at its close
│   ├── replay/         the server-side replay session (one cursor, many views)
│   │   ├── snapshot.py    one flat row: bar + indicator fields + drawings
│   │   ├── session.py     owns the cursor and live indicator state; publishes
│   │   ├── manager.py     sessions by id; reaps abandoned ones
│   │   └── routes.py      control (POST) + the SSE snapshot stream
│   ├── indicators/     state machines over the event stream
│   │   ├── base.py        what an indicator is; Unavailable (no proxy values)
│   │   ├── registry.py    topological order by dependency; merged field row
│   │   └── sessions.py    Asia/London/NY + running session extremes
│   ├── data/           load the NT8 Parquet store into clean bars — engine
│   │   ├── loader.py      read a symbol/TF Parquet -> raw UTC OHLCV (I/O)
│   │   └── prepare.py     window + gap-mark + zero-vol policy (logic)
│   ├── backtest/       resolve brackets against bars -> fills, PnL, stats
│   │   ├── bracket.py     Direction + Bracket (entry stop + SL/TP as absolute levels)
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
│   │   ├── history.py     fetch OHLCV bars for a contract
│   │   └── market_hub.py  live SignalR feed: GatewayTrade / GatewayQuote / Depth
│   ├── capture/        record the live feed so we can see what it sends
│   │   └── recorder.py    raw hub events -> JSONL, verbatim, one file per session
│   ├── chart/          serve bars to the browser chart (backend half)
│   │   ├── packer.py      Parquet -> flat 24-byte bar records in cache/chart/
│   │   ├── store.py       memmap the packed cache: slice bars, locate a time
│   │   ├── overlays.py    run indicators over a bar range -> drawing instructions
│   │   ├── api.py         route -> (status, content-type, bytes); no sockets
│   │   ├── server.py      HTTP: static frontend + /api, one port, no stacking
│   │   ├── lifecycle.py   single-instance guard; confirmed-closed shutdown
│   │   └── autoreload.py  dev: restart the server when Python changes
│   └── cli/            thin doors: parse input, call an engine, format out
│       ├── data.py        load & summarize prepared bars (python -m src.cli.data)
│       ├── chart.py       serve the replay chart (python -m src.cli.chart)
│       └── capture.py     record the live market feed (python -m src.cli.capture)
├── frontend/           browser code — never inside the Python src/
│   └── chart/          the replay chart (plain ES modules, no build step)
│       ├── index.html    toolbar + chart stage + OHLC readout
│       ├── css/chart.css dark, gridless theme
│       ├── vendor/       TradingView Lightweight Charts (vendored, not CDN)
│       └── js/
│           ├── main.js       wire the pieces; decides who talks to whom
│           ├── api.js        fetch + decode the binary bar records
│           ├── chart.js      the chart surface: rebuild (zoom-safe) / push
│           ├── browse.js     non-replay view; backfills older bars on scroll
│           ├── overlays.js   draw the backend's shapes; knows no indicator
│           ├── vertical_lines.js  chart primitive: dashed rules with labels
│           ├── format.js     time/price/volume display strings
│           └── replay/
│               ├── stream.js   EventSource + control POSTs to the session
│               ├── window.js   the bounded display buffer (append + trim)
│               ├── engine.js   subscribes to snapshots; owns no clock
│               └── controls.js toolbar -> engine wiring (the thin door)
├── BUILD_PLAN.md       the phased road to a live brain (read before a phase)
├── cache/              packed bar cache + server pidfile (git-ignored)
├── capture/            recorded live sessions, raw JSONL (git-ignored)
├── runs/               labeled run outputs (git-ignored): trades, summary, equity.png
├── tests/              pytest suite (dev tooling, not product code)
│   ├── test_fills.py       pins the fill model's honest assumptions
│   ├── test_chart_store.py pins the 24-byte wire format; slice/locate rules
│   ├── test_sessions.py    pins the session windows, the close-stamped
│   │                       boundary rule, and the indicator registry
│   ├── test_replay_session.py  pins seek == play-into, fan-out, no lookahead
│   └── test_lifecycle.py   pins per-port pidfiles; the Windows os.kill trap
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

backtest.engine   ─► backtest.fills      (resolve fills against a bar)
                  ├► backtest.bracket     (the order intent it consumes)
                  ├► config.backtest      (slippage, commission, hold policy)
                  └► config.instruments   (tick/point value for PnL)
backtest.runspec  ─► json                 (load the run config; a manifest replays)

reporting.stats   ─► backtest.engine      (the Trade type)
reporting.trades  ─► backtest.engine      (Trade -> CSV/text)
reporting.equity  ─► matplotlib, backtest.engine   (Trade -> PNG)
reporting.folds   ─► (walk-forward fold results -> CSV/text)
reporting.console ─► reporting.stats, core.console (terminal summaries)
reporting.run     ─► reporting.{trades,stats,equity,folds}, backtest.runspec  (labeled run)

optimize.sweep    ─► optimize.{grid,objective}, backtest.engine, reporting.stats
walkforward.engine ─► walkforward.folds, optimize.{sweep,objective}, backtest.engine,
                      reporting.stats, config.backtest

Neither optimizer nor walk-forward engine knows any strategy: both take a
``build(params) -> strategy`` callable. The caller owns the strategy catalogue;
the engines stay generic. A strategy is anything with ``entry_signals(bars)``
returning ``backtest.bracket.Bracket`` intents.

broker.market_hub ─► signalrcore, config.live   (live trades/quotes over websocket)
capture.recorder  ─► config.live                (raw hub events -> JSONL, verbatim)
cli.capture       ─► broker.{client,contracts,market_hub}, capture.recorder

The market hub sends TWO different things. ``GatewayTrade`` is executed trades
(a LIST per event: price, volume, timestamp, type); ``GatewayQuote`` is
top-of-book bid/ask, pushed on quote change, ~80x more frequent. A NinjaTrader
'Last' tick row is a trade with the prevailing quote stamped on it - i.e. the
join of the two. Subscribing to quotes alone yields no trades and every volume
indicator reads zero. On the quote, use ``lastUpdated`` (real event time), not
``timestamp`` (a constant session anchor); its ``volume`` is session-cumulative,
not per-event.

indicators.base      ─► (the Indicator interface + Unavailable)
indicators.registry  ─► indicators.base         (toposort deps; merged field row)
indicators.sessions  ─► config.session, indicators.base   (Asia/London/NY)
events.types         ─► (BarClose; Trade/Quote arrive with their sources)

chart.packer     ─► data.loader, numpy  (Parquet -> flat bar records)
chart.store      ─► chart.packer, numpy (memmap the cache; slice + binary-search)
chart.overlays   ─► chart.store, indicators.{registry,sessions}, config.indicators.sessions
chart.api        ─► chart.store, chart.overlays, config.chart   (routes -> bytes)

replay.session   ─► chart.{overlays,store}, config.{chart,replay}, replay.snapshot
replay.manager   ─► replay.session, config.replay   (registry + idle reaper)
replay.routes    ─► replay.manager, config.replay   (POST control; SSE stream)
chart.server     ─► replay.{routes,manager}         (dispatches /api/replay/*)

The replay cursor and the live indicator state live on the SERVER, not in the
browser. A step is a POST; bars arrive because the session published a Snapshot.
The chart subscribes to that stream and draws it; the TUI will subscribe to the
same stream and print it. One cursor, one computation, so two views cannot
disagree - and a third costs nothing. Seeking replays the warmup silently, so
the indicators at a cut point hold exactly what they would have held had you
played into it (pinned by tests/test_replay_session.py).
chart.server     ─► chart.{api,lifecycle,packer,autoreload}, config.chart  (HTTP + static)
chart.lifecycle  ─► config.chart        (pidfile, port probe, confirmed shutdown)
chart.autoreload ─► (watch .py mtimes; trip the server's stop event)
cli.chart        ─► chart.{server,packer,lifecycle}, logging.setup, core.console

The browser talks only to chart.api. Bars cross the wire as raw 24-byte records
(uint32 time + 5 float32s), never JSON - at 1m there are ~6M of them per symbol.
frontend/chart/js/api.js decodes that layout; tests/test_chart_store.py pins it.

The chart DRAWS; it never computes. There are no indicators in the frontend and
none may be added: indicators are computed once, in Python, and arrive over
/api/overlays as drawing instructions. One shape exists today: "vlines", a
dashed rule with a label, drawn by a lightweight-charts primitive onto the
chart's own canvas. overlays.js understands *shapes*, never meaning - it drops a
labelled rule without knowing what a trading session is, so the next indicator to
reuse that shape needs no frontend change at all.

The overlay request carries the REVEALED bar range, so indicators are fed only
bars at or before the replay cursor and a drawing cannot leak the future.

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
- **`python -m src.cli.chart`** — serve the replay chart at `http://127.0.0.1:8765`
  (`--open` also launches the browser once the socket is listening). Browse NQ/ES on
  any timeframe, or click a bar to cut back and replay forward bar by bar with
  play/pause and 1x/2x/4x. Zoom and pan stay live throughout. First run packs the bar
  cache (a few seconds); after that it is instant. `--repack` rebuilds it after new
  data lands; `--stop` closes a running server and confirms the port is free;
  `--reload` restarts the server whenever Python changes. HTML/CSS/JS need no
  flag - static files are read per request and sent `no-cache`, so a plain
  browser refresh picks them up. Each server records itself in a per-port
  pidfile (`cache/chart/server-<port>.pid`), so two servers on two ports can
  coexist and `--stop` only ever touches its own.
  Starting always reclaims the port, so servers never stack. Wired into
  `commands.bat` → Chart. **The page must be served — opening `index.html` from the
  filesystem cannot work** (`file://` has no origin, so the module and API fetches
  are blocked).

The backtest and walk-forward doors were removed with the strategy layer; they
return when the new strategy layer lands (a door wires its catalogue into the
engines' ``build`` callable).

- **`python -m src.cli.capture --seconds N`** — record the live market feed for one contract to `capture/<stamp>_<contract>.jsonl`, one raw event per line with a local receipt timestamp. It interprets nothing: the ProjectX docs name the hub events but do not document their payloads, so we record first and write the adapter against what the feed really sends. A recording also serves as a test fixture (drives the live code path with no network) and as the only way to check whether TopstepX's stream agrees with the NinjaTrader tick export. Wired into `commands.bat` → Live.

`broker/` is a verified, reusable engine (auth → account → contract → bars) still awaiting its own command (e.g. live trading, health check); when built it adds another thin `cli/` door here, wired into `commands.bat`.

## Note on API history depth

`retrieveBars` is **per-contract**. The active NQ contract (`CON.F.US.ENQ.U26`) only serves ~1 month of history (verified: back to ~2026-06-07). The API is a *recent-data* source, not deep history — multi-year continuous history is the NT8 Parquet in `data/`. Building a continuous series would require stitching successive quarterly contracts.

## Backtest data reference

The historical NQ/ES Parquet in `data/` is audited in `DATA_AUDIT.md` (human) and `DATA_AUDIT.json` (machine). `audit/reader.py` is the code that reads that JSON; `config/instruments.py`, `config/session.py`, and `config/backtest.py` turn its fixed facts (contract specs, timezone, `handling` flags) into the dials the backtest engine runs on. Data is clean; the flags (gap-awareness, back-adjustment, fills/slippage, staleness) are what the engine must honor — they now live as config, seeded from the audit.

## Not built yet (planned shape)

**The strategy layer is being redefined and is currently absent.** The engines it
plugs into (`backtest/`, `optimize/`, `walkforward/`, `reporting/`) are intact and
strategy-agnostic. What returns: a strategy package emitting `Bracket` intents from
`entry_signals(bars)`, whatever indicators it needs, its run configs, and the thin
`cli/` doors that wire a catalogue into the engines' `build` callable.

These get created — with their config section alongside — when the area is actually built: `broker/orders.py`, `broker/positions.py`, `risk/` (sizing/limits, reads `config/risk.py`), `execution/` (live loop, reads `config/live.py`), `config/risk.py`. (`data/`, `backtest/`, `chart/`, and `cli/` now exist.)

`frontend/chart/` is plain ES modules with no build step and no package.json — the
browser loads them directly and the one dependency is vendored. If a real build
pipeline is ever needed, it belongs to `frontend/`, never to the Python `src/`.
