# BUILD_PLAN.md — the road to a live trading brain

**Read this before starting a phase.** It records what we decided, what we verified, and
what order we build in. `ARCHITECTURE.md` says how today's code is wired; this says where
it is going and why.

**We go slow, on purpose.** One phase at a time. Each phase ends with something Jake can
*look at* and form an opinion about — because most of the remaining design questions
cannot be answered in the abstract, only by staring at real output. A phase is done when
it is built, verified, committed, and Jake has seen it. Then we talk, then the next one.

---

## The shape of the finished thing

```
   event source            indicators              snapshot            brain            execution
 ┌──────────────┐      ┌────────────────┐      ┌───────────┐      ┌──────────┐      ┌───────────┐
 │ bars (20yr)  │      │ sessions       │      │           │      │ scores   │      │ place     │
 │ ticks (2.3yr)│ ───► │ structure      │ ───► │  one row  │ ───► │ decides  │ ───► │ bracket   │
 │ live (SignalR)      │ volume / delta │      │ per event │      │ a signal │      │ + manage  │
 └──────────────┘      │ regime         │      └───────────┘      └──────────┘      └───────────┘
                       └────────────────┘            │
                                                     ├──► replay chart  (draws the row)
                                                     └──► TUI table     (prints the row)
```

Jake's words: *"snapshot, brain/decider, execution, manage."* That is the spine.

---

## Decisions already made (do not relitigate without a reason)

**Abstract over events, not over bar-ness.** A tick is `(ts, price, bid, ask, size)`. A bar
close is `(ts, ohlcv)`. Both are timestamped things arriving in order. An indicator is a
**state machine** that consumes events and exposes current state. The same indicator code
then runs over bars, over ticks, and over the live feed. Backtest, replay, and live differ
only in which source feeds them and what paces the clock.

**Code portability is not information portability.** Total volume is in bars and is
accurate. *Signed* volume (delta), absorption, sweeps, and spread are **not recoverable
from bars** — that information was never written down. A tick-only indicator fed bars must
**refuse to produce a number**, never a proxy. A proxy delta is worse than no delta,
because the backtest will trust it.

**The backend computes; the frontend draws.** There is exactly one implementation of every
indicator, in Python. The chart and the TUI are two *renderers* of the same rows, so they
cannot disagree. Any indicator math in JavaScript is a bug — it will drift, and the day it
drifts is the day a chart contradicts a backtest.

**A snapshot is one flat row.** Named fields, stamped with **market time**, immutable,
built only from events at or before its timestamp. The history of snapshots is a table —
which is precisely the TUI view, and precisely what the brain reads. Same object, two
consumers. Because it is built only from past events, an indicator **cannot see past the
replay cursor**. No-lookahead is a property of the structure, not a rule we remember.

**Judgment is just another field.** `delta` is a field. `absorption`, computed from `delta`
and `range`, is a field. `regime: consolidation`, computed from those, is a field. Raw
values and interpretations are not two systems; they are layers of one. Indicators that
read other indicators declare their dependencies and are topologically sorted at startup;
a cycle is a startup error, not a garbage number.

**Cadence is a dial, not a decision.** Indicators *update* on every event. A snapshot is
*emitted* on a trigger: bar close, per trade, or every N ms. Config, not architecture.
(Quotes outnumber trades roughly 80:1 overnight, so "per quote" is rarely what you want.)

---

## What we verified against the real data (facts, not assumptions)

**Bars** (`data/NQ/`, `data/ES/`) — 2005-01-11 → 2025-01-10. NQ 1m is 6,225,528 bars.
- **Close-stamped.** Bar `T` covers `(T-Δ, T]`. Confirmed: 1m aggregates into 5m exactly,
  OHLC *and* volume, 4/4 samples, using `closed='right', label='right'`.
- Volume **is** present and accurate (129 zero-volume bars out of 6.2M on NQ 1m).
- Back-adjusted continuous series; absolute levels before the current contract are synthetic.

**Ticks** (`NQ_Tick_Data/`) — 10 contracts, 2024-03-12 → 2026-07-03, ~300M ticks.
- **UTC**, despite the README saying "exchange time." Proven: the only empty hour is
  21:00–22:00 UTC (the CME maintenance halt) and volume explodes at 13:30 UTC (the RTH open).
- **52% of ticks share a timestamp with a neighbour.** Timestamps are **not unique keys**.
  Never dedup on time, never index on time alone; preserve file order among ties.
  (This bit us once already — an `idxmax` tie-break silently picked the wrong close.)
- Every trade prints at the bid or the ask; **0.00% print between**. Aggressor
  classification is unambiguous. Spread: median 0.50 pts, p99 4.00.
- **Reconciled against NT8's own bars** over `NQ 12-24` (89,218 overlapping 1m bars):
  high/low match 99.7%, all five fields match 91.0%, and **total volume differs by 363
  contracts out of 31,342,710 — 0.0012%.** Back-adjustment offset is a clean `+1204.00`.
  The residual is one-tick edge assignment; NT8's bar file and tick DB are not built
  bit-identically, and no lag correction fixes it. **The tick data is trustworthy.**
  → Build every timeframe from ticks, self-consistently. Do not mix tick-built bars with
  the NT8 bar file. A tick-driven backtest will not exactly reproduce a bar-driven one.

**Why bars cannot fake order flow** — measured, on 1,371 tick-built 5m bars:
`correlation(bar body, delta) = 0.746`, so the candle explains 56% of delta. **17.9% of
bars close in the opposite direction to their net order flow.** Two bars matched to within
one tick of body, six ticks of range, 2.5% of volume, and six prints — differed by **1,326
contracts of delta.** The projection from ticks to a bar is not injective and has no inverse.

**Live feed** (TopstepX SignalR market hub) — recorded, 254 events in 25s.
- `GatewayTrade` → `[contractId, [ {symbolId, price, timestamp, type, volume, contractId}, … ]]`
  — a **list** of trades, and **no bid/ask**.
- `GatewayQuote` → `[contractId, {bestBid, bestAsk, lastPrice, open, high, low, volume,
  lastUpdated, timestamp, …}]` — pushed on quote change, ~80× more often than trades.
- An NT8 `Last` tick row **is** a trade with the prevailing quote stamped on it. The live
  source must hold the last quote and join. Subscribing to quotes alone yields no trades
  and every volume indicator reads zero.
- On the quote, use **`lastUpdated`** (real event time). `timestamp` is a constant session
  anchor. Its `volume` is **session-cumulative**, not per-event.
- **Open question:** `GatewayTrade.type` may be the aggressor side. If so, TopstepX gives
  signed volume directly and delta needs no bid/ask inference. Only 3 trades arrived on a
  quiet overnight tape. **Needs an RTH capture** (13:30–20:00 UTC) to correlate `type`
  against `bestBid`/`bestAsk`.

---

## Phases

Each phase is small, ends in a commit, and ends with something to look at.
**Do not start a phase before the previous one has been seen and approved.**

### Phase 1 — the chart, correct  *(done — f926b4f)*
Make the existing replay chart honest before anything is layered on it.

- Remove all indicator math from JavaScript. The chart draws; it does not compute.
- Keep what already works: dark/gridless theme, browse mode with scroll-back backfill,
  replay (cut back by click or datetime, step, play/pause, 1×/2×/4×), free zoom throughout,
  the bounded bar window with prefetch-ahead and trim-behind, and the visible-range shift
  that keeps a trim from jumping the view.
- **Done when:** the chart is clean, fast, and has no second implementation of anything.

### Phase 2 — one indicator, end to end  *(built — awaiting review)*
The narrowest possible slice through the whole spine.

Two bugs found by measuring, before a line of it was written:
- `config/session.py` paired **Eastern** window numbers with `America/Chicago`. That
  discarded 5,764 real trading bars (the 17:00-18:00 ET hour) into no session at all,
  and mislabelled the maintenance halt as NY. Fixed to `US/Eastern`; now every one of
  143,013 bars falls in exactly one session.
- Session membership must be `start < minute <= end`, because bars are close-stamped.
  With `minute < end` the 17:00 ET bar - NY's last - belongs nowhere.

Also: converting each timestamp to Eastern cost 85ms of a 125ms indicator pass. US
offsets are whole hours and DST flips on a UTC hour boundary, so the offset is cached
per UTC hour (exact, not approximate). Overlays for 8,000 bars: 187ms -> 58ms.

- The indicator interface: a state machine (`update(event)` → fields) with declared
  dependencies and a per-indicator config file under `src/config/indicators/`.
- **Sessions first** — pure time, cannot be subtly wrong, and instantly visible.
- A backend endpoint that serves the indicator's output alongside the bars, and a
  **renderer** on the chart that draws whatever spec the backend sends (line / band /
  marker) without knowing what a session is.
- **Done when:** Jake sees the sessions marked on the chart in browse *and* replay, drawn
  from values Python computed, with a config file he can edit.
- Shipped: a dashed labelled rule at each session open (a lightweight-charts primitive, so
  it tracks pan and zoom exactly), and `--reload` so a Python edit restarts the server.
  Static files already reload on a plain browser refresh.

### Phase 3 — the snapshot row and the TUI table
- The snapshot: one flat, immutable, market-time-stamped row of named fields.
- The registry: indicators declare fields and dependencies; topological sort; emit trigger
  from config.
- The TUI: a horizontal table, one row per emitted snapshot, columns scrolling as price
  moves. **Wired into replay** — it runs *with* the chart, off the same backend, so Jake
  can watch the drawings and the numbers agree in real time.
- **Done when:** chart and TUI run together during a replay and tell the same story.

### Phase 4 — indicators in volume
Structure, volume, delta, absorption, regime. One at a time, each with its config, each
appearing as a column in the TUI and (where it makes sense) a drawing on the chart.
Tick-only indicators refuse to produce values when fed bars.

### Phase 5 — the clock-driven replay engine
Replace the bar-index cursor with a **market-time clock**. A step advances time; every
timeframe is a fold over events at or before the clock. This is what unlocks:
- tick-resolution replay (stepping *one tick* is meaningless — 20,065 prints landed in the
  13:30 minute alone; replay must advance market time and apply the batch),
- several timeframes on screen at once (they share a clock, not an index),
- the forming higher-timeframe candle, built from the ticks seen so far.
Backwards seek replays silently from `T − warmup` so indicator state is correct at the cut
with no lookahead. The same silent-replay primes indicators when a live session starts.

### Phase 6 — the brain
Reads snapshots (latest plus a bounded ring of recent ones), scores them, decides a signal.
**Do not design this yet.** Jake cannot describe the scoring because he has not seen the
rows, and nobody could. The rows will describe it.

### Phase 7 — execution and management
Place the bracket (entry stop, stop loss, target); a separate module manages the open
position. `backtest/bracket.py` already defines the order intent, and the engine consumes
it — that vocabulary is deliberately independent of any strategy.

---

## Standing work, not a phase

- **Tick audit** (`TICK_AUDIT.md`, in the spirit of `DATA_AUDIT.md`): the 52% timestamp
  collision rate, spread distribution and whether the wide tail is stale quotes or thin
  markets, zero/negative volumes, roll seams across the 10 contracts, and whether
  `GatewayTrade.type` agrees with bid/ask classification where both exist.
- **RTH live capture** to settle the `type` question. `python -m src.cli.capture --seconds 300`
  between 13:30 and 20:00 UTC.
- **15s and the rebuilt timeframes.** 15s exists only where ticks exist. The stitched tick
  file is now **built**: `NQ_continuous_ticks.parquet`, **296,029,228 ticks**, 2.0 GB,
  2024-03-12 → 2026-07-03, all 10 contracts back-adjusted across roll seams of +212 to
  +286 points. Next: rebuild 15s/1m/5m/15m/1h/4h from it for the tick window. The 20-year
  bar history remains its own dataset for bar-expressible work.

---

## Traps we have already paid for

- `os.kill(pid, 0)` is **not** an existence probe on Windows — CPython implements `os.kill`
  there as `TerminateProcess`, so the "probe" kills the process it asks about.
- `HTTPServer.allow_reuse_address = True` on Windows lets a **second** process bind a port
  that is already being listened on. That is how servers stack.
- Tick timestamps are not unique (52% collide). Tie-breaking with `idxmax` on time picks
  the *first* row of a tie, not the last, and silently corrupts a bar's close.
- The chart page **must be served**. `file://` has a null origin, so the ES modules and the
  `/api/*` fetches are both blocked.
