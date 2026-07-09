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
│   │   ├── ticks.py       tick file path, rebuilt-bar symbol + timeframes
│   │   ├── replay.py      session idle timeout, subscriber queue, speeds
│   │   ├── table.py       desktop table: server URL, row cap, theme
│   │   ├── live.py        contract id, which market streams, capture dir
│   │   ├── profile.py     volume-at-price cache dir, tick size, value-area share
│   │   └── indicators/    one module per indicator, named for its id
│   │       ├── sessions.py  enable + line colors for the sessions indicator
│   │       ├── orderflow.py enable + delta strip colors and placement
│   │       ├── absorption.py thresholds + marker colors
│   │       ├── range_scale.py window in MINUTES of market time, floored in bars
│   │       ├── swing.py     retrace threshold (multiples of range_scale)
│   │       ├── legs.py      staircase colors (muted: a leg is not news)
│   │       ├── breaks.py    close-vs-wick definition + break colors
│   │       └── profile.py   bin width, how many closed profiles to keep
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
│   ├── table/          a desktop window of snapshot rows (second subscriber)
│   │   ├── client.py      find/attach a session; read its SSE stream (no Qt)
│   │   ├── columns.py     snapshot -> cells, grouped by producer; facts vs detail
│   │   └── window.py      the Qt table: never wraps, follows with escape
│   ├── replay/         the server-side replay session (one cursor, many views)
│   │   ├── snapshot.py    one flat row: bar + indicator fields + drawings
│   │   ├── session.py     owns the cursor and live indicator state; publishes
│   │   ├── manager.py     sessions by id; reaps abandoned ones
│   │   └── routes.py      control (POST) + the SSE snapshot stream
│   ├── indicators/     state machines over the event stream
│   │   ├── base.py        what an indicator is; Unavailable (no proxy values)
│   │   ├── registry.py    topological order by dependency; merged field row
│   │   ├── sessions.py    Asia/London/NY + running session extremes
│   │   ├── orderflow.py   delta/buy/sell/trades, or Unavailable on bar files
│   │   ├── absorption.py  closed against its own flow; depends on orderflow
│   │   ├── range_scale.py rolling median bar range - the adaptive unit
│   │   ├── swing.py       confirmed structure points + the live high/low rails
│   │   ├── legs.py        the staircase from one swing to the next
│   │   ├── breaks.py      a swing level closed through: break of structure
│   │   └── profile.py     the developing profile; frozen onto each structure
│   ├── profile/        volume at price - what bars can never carry
│   │   ├── build.py       ticks -> 1-tick histograms, packed (I/O + fold)
│   │   ├── store.py       memmap the pack; slice a time range -> histogram
│   │   └── value_area.py  histogram -> POC / VAL / VAH (pure, no I/O)
│   ├── data/           load the NT8 Parquet store into clean bars — engine
│   │   ├── loader.py      read a symbol/TF Parquet -> raw UTC OHLCV (I/O)
│   │   ├── prepare.py     window + gap-mark + zero-vol policy (logic)
│   │   └── resample.py    ticks -> bars + order flow (delta/buy/sell/trades)
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
│       ├── resample.py    rebuild bars from ticks (python -m src.cli.resample)
│       ├── table.py       desktop snapshot table (python -m src.cli.table)
│       ├── chart.py       serve the replay chart (python -m src.cli.chart)
│       ├── vap.py         build volume at price (python -m src.cli.vap)
│       ├── fields.py      the field contract (python -m src.cli.fields)
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
│           ├── segments.js   chart primitive: polylines in (time, price) space
│           ├── format.js     time/price/volume display strings
│           └── replay/
│               ├── stream.js   EventSource + control POSTs; detects a retired
│               │               session instead of reconnecting at it forever
│               ├── window.js   the bounded display buffer (append + trim)
│               ├── engine.js   subscribes to snapshots; owns no clock;
│               │               re-seeds itself when its session is retired
│               └── controls.js toolbar -> engine wiring (the thin door)
├── BUILD_PLAN.md       the phased road to a live brain (read before a phase)
├── FIELDS.md           GENERATED: field -> indicator -> source + config file
├── cache/              packed bar cache + server pidfile (git-ignored)
├── capture/            recorded live sessions, raw JSONL (git-ignored)
├── runs/               labeled run outputs (git-ignored): trades, summary, equity.png
├── tests/              pytest suite (dev tooling, not product code)
│   ├── test_fills.py       pins the fill model's honest assumptions
│   ├── test_chart_store.py pins the 24-byte wire format; slice/locate rules
│   ├── test_sessions.py    pins the session windows, the close-stamped
│   │                       boundary rule, and the indicator registry
│   ├── test_replay_session.py  pins seek == play-into, fan-out, no lookahead
│   ├── test_resample.py    pins the tick->bar rebuild: ties, chunk seams, roll
│   ├── test_orderflow.py   pins the rule that absent is never zero
│   ├── test_absorption.py  pins the definition + the dependency ordering
│   ├── test_swing.py       pins scale invariance: 10x the prices, same swings
│   ├── test_fields.py      pins the contract; fails when FIELDS.md goes stale
│   ├── test_profile.py     pins the value area: contiguous, grown from the POC
│   ├── test_profile_indicator.py  pins the freeze: at the bar that MADE the swing
│   ├── test_structure.py   pins legs + breaks: a level fires once; a swing's
│   │                       own confirming bar can never break it
│   ├── test_table_columns.py  pins row rendering: absent != zero, colour rules
│   ├── test_table_client.py   pins the reconnect storm: backoff, adoption
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

data.resample    ─► pyarrow, config.ticks   (296M ticks -> bars, streamed once)
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
not per-event. A quote update need not carry both sides - 211 of 508 arrived with
no bestBid or bestAsk - so a live source holds the last known value PER SIDE.

``GatewayTrade.type`` IS the aggressor side: **0 = aggressive buy** (lifted the
ask), **1 = aggressive sell** (hit the bid). Live delta MUST be read from it, and
must never be inferred from ``GatewayQuote``: that feed is conflated (13 msgs/sec
against 8 trades/sec; a 0.75pt spread on 60% of quotes where NQ trades one tick;
40.7% of trades print outside the quoted bid/ask). Inferring live delta from the
quote would inject a systematic ~7% misclassification that the historical
pipeline - which reads NinjaTrader's exchange-stamped bid/ask, 0.0005% mid-spread
- does not have, and live would quietly disagree with the backtest.

Trades arrive BATCHED: one ``GatewayTrade`` carried up to 34 of them. Iterate
``payload[1]``; never read ``payload[1][0]``.

``GatewayLogout`` fires and is currently unhandled; a long-running feed must
treat it as end-of-session and re-authenticate.

indicators.base      ─► (the Indicator interface + Unavailable + provenance())
indicators.registry  ─► indicators.base         (toposort deps; merged field row)
cli.fields           ─► chart.overlays, table.columns   (the field contract)

Every field in the snapshot row is published by exactly ONE indicator, and
`Indicator.provenance()` derives from the class itself where its code and its
dials live. `python -m src.cli.fields` prints that contract; `--write` regenerates
FIELDS.md, and `tests/test_fields.py` fails if the file goes stale. The desktop
table colours each column block by its producing indicator, with a legend - the
same map, on screen.
indicators.sessions  ─► config.session, indicators.base   (Asia/London/NY)
indicators.orderflow ─► indicators.base   (lifts delta off the bar; refuses if absent)
indicators.absorption ─► indicators.base, config.indicators.absorption
                         (depends on `orderflow`; reads delta, never recomputes it)
indicators.range_scale ─► indicators.base, config.indicators.range_scale
                         (rolling median bar range; window in market MINUTES with a
                          bar-count floor; refuses on a dead tape and while warming)
indicators.swing     ─► indicators.base, config.indicators.swing
                         (depends on `range_scale`; retrace measured in it, never in points)
indicators.legs      ─► indicators.base   (depends on `swing`; joins consecutive points)
indicators.breaks    ─► indicators.base, config.indicators.breaks
                         (depends on `swing`; a level closed through, fired once)

indicators.profile ─► profile.{store,value_area}, config.indicators.profile
                      (depends on `range_scale` for its bin width and on `swing`
                       for the range; refuses on a bar with no volume at price)

profile.build      ─► data.resample (anchor + aggressor), config.{profile,ticks}
profile.store      ─► profile.build (the packed dtypes), config.profile, numpy
profile.value_area ─► config.profile, numpy    (POC/VAL/VAH; pure, no I/O)
cli.vap            ─► profile.build, profile.store, core.{console,progress}

A bar records total volume, its high and its low - never WHERE inside that range
the contracts changed hands. Spreading a bar's volume across its range would be a
fabrication, and the profile drawn from it a picture of the assumption. So volume
at price is folded from the tick file once (296M ticks -> 35.3M levels across
1.62M 30s bars, 81s) into a packed store the chart memmaps and slices. Bins are
ONE TICK wide because that is the finest the market resolves - after
back-adjustment 100.00% of prices land on the 0.25 grid - and every coarser
binning is an exact fold of it. `python -m src.cli.vap --verify` checks each
sampled bar's histogram against that bar's own volume; a single lost contract
would make every profile quietly wrong and no picture would show it.
events.types         ─► (BarClose; Trade/Quote arrive with their sources)

Exactly one number in that chain adapts, and it enters once. `swing` confirms at
`RETRACE x range_scale`; `legs` is pure geometry between two swing points and
`breaks` is an exact price comparison against one. Neither carries a threshold of
its own, so scale invariance propagates to them for free - verified on 54,593 real
15m bars: multiply every price by ten and the same 580 swings, 579 legs and 248
breaks come out.

`range_scale` is the denominator the rest of the system is meant to grow into.
NQ's median 30s bar range swung 3.17x across 29 months, so any threshold written
in points is right for one regime and wrong for the next. A rolling estimate is
possible only because bar range is persistent (the last 60 bars' median predicts
the next 60 at r = 0.65). `swing` is the first consumer: its retrace threshold is
`RETRACE x range_scale`, which makes the structure it finds invariant to how loud
the market is. Multiply every price by ten and the same swings appear - pinned by
`tests/test_swing.py`.

chart.packer     ─► data.loader, numpy  (Parquet -> flat bar records)
chart.store      ─► chart.packer, numpy (memmap the cache; slice + binary-search)
chart.overlays   ─► chart.store, indicators.{registry,sessions,orderflow,absorption,
                    range_scale,swing}, config.indicators.*
chart.api        ─► chart.store, chart.overlays, config.chart   (routes -> bytes)

replay.session   ─► chart.{overlays,store}, config.{chart,replay}, replay.snapshot
replay.manager   ─► replay.session, config.replay   (registry + idle reaper)
replay.routes    ─► replay.manager, config.replay   (POST control; SSE stream)

A replay session has an OWNER - a stable id the browser keeps in localStorage.
Starting a replay retires every session that owner left behind, which is what
stops a page refresh (or a --reload restart) stranding orphans until the idle
reaper notices. `replace` handles the id the caller still remembers; `owner`
handles the ones it has forgotten.
chart.server     ─► replay.{routes,manager}         (dispatches /api/replay/*)

table.client     ─► urllib, config.table  (find a session; read its SSE stream;
                     back off on reconnect; adopt the session that replaced it)
table.columns    ─► config.table      (snapshot -> cells; pure, no Qt)
table.window     ─► PySide6, table.columns, config.table
cli.table        ─► table.{client,window}

The desktop table is a SECOND SUBSCRIBER to the session the chart is driving. It
cannot step the cursor and cannot disagree with the chart: the same Snapshot
object is delivered to both. Its columns are not configured anywhere - the fixed
six describe the bar, the rest are whatever fields the session reports, so a new
indicator grows a new column with no edit to the table.

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
(uint32 time + 9 float32s, 40 bytes), never JSON - at 1m there are ~6M of them.
The four order-flow fields are NaN when the dataset cannot supply them, decoded
to `null` in the browser and `None` in Python. Absent is not zero: packing 0 for
the NT8 bar files would tell every indicator that twenty years of history had
perfectly balanced buying and selling.
frontend/chart/js/api.js decodes that layout; tests/test_chart_store.py pins it.

The chart DRAWS; it never computes. There are no indicators in the frontend and
none may be added: indicators are computed once, in Python, and arrive over
/api/overlays as drawing instructions. Four shapes exist: "vlines" (a dashed rule
with a label), "markers" (a dot on a bar), "segments" (a polyline through
(time, price) corners), and "levels" (a price line across the pane). The first and third are lightweight-charts primitives
drawing onto the chart's own canvas, so they track every pan and zoom exactly.
overlays.js understands *shapes*, never meaning - it drops a labelled rule without
knowing what a trading session is, a dot without knowing what absorption is, and a
polyline without knowing what a break of structure is. Both `legs` and `breaks`
landed on the chart by reusing "segments"; the next indicator to reuse any of the
three needs no frontend change at all.

A mark carries a `source`, and group_marks emits one spec per source, so a spec
stays named after one job: "breaks" never carries someone else's lines. A segment
is stamped with its EARLIEST point, because that is what the replay trim compares
against - a polyline whose left end has scrolled out of the buffer must be dropped
rather than half-drawn, and the primitive likewise skips any corner it cannot place.

A mark may also carry an `id`, and that changes what it *is*. Without one it is an
EVENT - a swing, a leg, a break - and it accumulates. With one it is a REDRAW of a
running state: `swing`'s provisional rails are re-emitted on every bar, one bar
longer, and the newest pair replaces the last. `overlays.collapse_redrawn` does it
server-side (walking 3,000 bars yields two rails, not six thousand) and
`engine.js` does it in the browser as snapshots arrive.

A mark may instead carry a `layer`, and then the whole GROUP is redrawn: only the
marks from the last bar that emitted that layer survive. The volume profile
publishes a different number of bins on every bar, so matching them by id would
leave ghost bins behind from a range that has since been reset. The profile added
no frontend at all - a histogram bin is a `segment`, and a shape vocabulary earns
its keep when the fourth indicator to reach the chart needs nothing new.

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

- **`python -m src.cli.table`** — a desktop window (PySide6) showing each replay snapshot as
  a row: the bar, every indicator field, colour-coded. It attaches to the replay the chart is
  already driving, so the drawings and the numbers move together. It never wraps — columns clip
  and the view scrolls horizontally, per pixel — and it follows the newest row until you scroll
  up, then holds position and counts what has landed. Start a replay on the chart first, or pass
  `--symbol NQT --timeframe 5m` to start one. Wired into `commands.bat` → Chart.

`broker/` is a verified, reusable engine (auth → account → contract → bars) still awaiting its own command (e.g. live trading, health check); when built it adds another thin `cli/` door here, wired into `commands.bat`.

## Two bar datasets, deliberately kept apart

`data/NQ/`, `data/ES/` are the **NT8 bar files**: 2005-01-11 → 2025-01-10, OHLCV only.
`data/NQT/` are **bars rebuilt from ticks**: 2024-03-12 → 2026-07-03, at 15s/30s/1m/5m/15m/60m/4h,
and each bar additionally carries `delta`, `buy_volume`, `sell_volume`, `trades`.

They live under different symbols on purpose. The two series are back-adjusted from
different anchors, so their absolute prices are **not comparable** — `NQT` re-anchors so the
newest contract keeps its real prices (offset `+2187.00`). Never mix them in one series.

Only `NQT` can carry order flow. A bar file records total volume, not which side was the
aggressor; that information is destroyed by aggregation and no transformation recovers it.
`15s` exists only in `NQT` for the same reason — bars cannot be subdivided.

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
