# FIELDS_V3.md — the system, and what in it can be overfit

**Hand-written, unlike `FIELDS.md` and `FIELDS_V2.md`.** Those two are generated
by `python -m src.cli.fields --write` and say *what every field is*. This one is
reasoned, says *how the whole thing fits together and what it costs in degrees of
freedom*, and `--write` does not touch it. When the counts below drift, they are
re-derived by hand — the method for each is written beside it so they can be.

Every number here was measured against the code on 2026-07-16, not estimated.

---

## 1. The shape of it

One pipeline, four surfaces. Nothing else exists.

```
   bars (parquet)          NQ / ES from NT8 · NQT rebuilt from ticks (+ delta)
        |
   indicators/             12 state machines, topologically ordered
        |                  each reads the row so far, appends its own fields
        v
   ONE FLAT ROW            76 fields · replay/snapshot.py · the whole contract
        |
        +----> chart          draws it            (frontend/chart)
        +----> table          tabulates it        (src/table)
        +----> session card   summarizes it now   (frontend session panel)
        +----> catalog        66,625 rows of it   (session_history/catalog.py)
        |
        v
   [ THE BRAIN ]          <- does not exist. src/strategy/ is an empty folder.
        |
   [ risk / execution ]   <- does not exist. broker/ is read-only: no orders.py.
```

**The row is the interface, and that is the load-bearing fact of the design.**
The chart, the table, the card and the catalog are all *subscribers* to the same
server-side row. A brain is just a fifth subscriber. In a backtest the same rows
come out of a bar loop instead of a replay — same shape, same brain, no
translation layer. That is what will make backtest and live *provably* the same
system rather than two systems you hope agree. The moment the brain reads
anything the row did not hand it, they diverge forever and nothing will say so.

---

## 2. The menu — 89 runnable commands

`commands.bat` launches `commands.ps1`. Verified by loading the tree and walking
it, not by grepping labels.

| group | commands | what it is |
|---|---:|---|
| Setup | 1 | install dependencies |
| Chart | 13 | the chart server, the table, the session picker |
| Live | 3 | record the TopstepX feed verbatim |
| Data | 7 | build bars, VAP, the percentile table, the catalog |
| **Analysis** | **61** | ten submenus — see below |
| Maintenance | 4 | regenerate docs, audit the project |

The 61 Analysis items are grouped by **what a thing is for**, not what it studies:

| submenu | n | why it exists |
|---|---:|---|
| Session research | 2 | the VPbreakout workflow — today's work |
| Calibration | 4 | **the receipts**: why a live dial is the number it is |
| Structure | 11 | swings, legs, breaks |
| Profile & value area | 6 | |
| Moving averages & regime | 10 | |
| Order flow | 2 | |
| Edges tested | 11 | pre-registered studies, most of them killed |
| Papers | 7 | the written-up findings |
| Recurrence & geometry | 5 | |
| Views | 3 | drawings, not findings |

**Calibration is not clutter — delete it and measured numbers become guesses.**
Five scratch scripts are cited *by live config* as the reason a dial holds its
value:

| script | justifies |
|---|---|
| `analysis/scale_ladder.py` | `swing.RETRACE = 3.0` (the H = 0.503 result) |
| `analysis/seasonality_report.py` | `range_scale.WINDOW_MINUTES = 30` |
| `analysis/ribbon_regime.py` | `regime`'s four cutoffs |
| `session_research/session_window_study.py` | `session_stats.RECENT_MIN_BARS = 6` |
| `session_research/seal_split.py` | wrote `SESSION_SPLIT.json` |

### The doors (10)

`python -m src.cli.<name>`: `chart` · `table` · `data` · `resample` · `vap` ·
`capture` · `fields` · `session_history` · `session_catalog` · `explore_session`.
There is no `main.py` anywhere, deliberately — nine thin doors instead of one
god-file.

---

## 3. The fields — 76, of which 50 are shown

Counted by importing every indicator and reading its `fields` tuple.

| indicator | fields | shown | detail | depends on |
|---|---:|---:|---:|---|
| `sessions` | 2 | 2 | 0 | the bar |
| `range_scale` | 1 | 1 | 0 | the bar |
| **`session_stats`** | **27** | **22** | 5 | `sessions`, `range_scale` |
| `orderflow` | 4 | 4 | 0 | the bar |
| `absorption` | 2 | 2 | 0 | `orderflow` |
| `swing` | 10 | 5 | 5 | `range_scale` |
| `legs` | 5 | 0 | 5 | `swing` |
| `breaks` | 3 | 1 | 2 | `swing` |
| `ribbon` | 2 | 0 | 2 | the bar |
| `regime` | 5 | 4 | 1 | `ribbon` |
| `ma` | 2 | 2 | 0 | the bar |
| `profile` | 13 | 7 | 6 | `swing`, `range_scale` |
| | **76** | **50** | **26** | |

Plus 6 bar columns (time, OHLC, volume) that every view always shows — they are
the time and price everything else is located against.

**`session_stats` is 27 of 76 — more than a third of the system's entire field
surface sits in one indicator.** That is the VPbreakout card, and it is where all
the current work is.

### The card, by job

| job | fields |
|---|---|
| **shape** | `session_range` `session_bars` `session_net` `session_net_ratio` `session_closed_ratio` `session_high_at_ratio` `session_low_at_ratio` |
| **phase** (recent vs prior) | `session_efficiency_recent` `session_efficiency_prior` `session_range_ratio` `session_volume_ratio` `session_dir_change_rate` |
| **flow** | `session_volume` `session_delta_recent` |
| **levels** | `session_poc` `session_poc_ratio` `session_val` `session_vah` `session_hvn`* `session_lvn`* |
| **vs history** | `session_range_percentile` `session_travel_percentile` `session_volume_percentile` `session_travel_budget` |

\* detail — a list of prices, not a single fact.

Three design decisions worth restating, because each cost real debugging:

- **No body/wick split.** It would be three lines computed from the two above
  them: `open_ratio = closed_ratio − net_ratio` always. Same facts, told twice.
- **Nothing is open-to-now except shape.** Efficiency, direction changes and
  travel were session-cumulative and *silently failed* on any session with two
  characters: a crash-then-base session read `efficiency 0.33`, the blend of a
  ~1.0 impulse and a ~0.1 base, describing neither. The recent/prior pair
  replaced them. Aggregates over a bimodal session do not error — they return a
  plausible number pointing the wrong way.
- **Delta is windowed, never cumulative.** A cumulative sum of a *signed*
  quantity across regimes does not average them, it **cancels** them. A real
  session: 211K volume, a genuine crash, genuine dip-buying, net delta −3K,
  which read as "no conviction" when conviction happened twice.

### Reading it out

```
Chart -> Pick a session to study        # random, explore-side, never the vault
Chart -> Open chart                     # paste the timestamp, Go
Chart -> Snapshot table - session card only
```

Select rows, **Ctrl+C** → a markdown table with a context line, raw field keys,
and only the columns shown. That is the paste-to-an-analyst loop.

---

## 4. The parameter census

Every module-level constant in `src/config`, classified by AST walk.

| class | n | can it be overfit? |
|---|---:|---|
| Cosmetic — colors, widths, pixels, draw flags | 101 | **No.** Changes a picture, never a number. |
| Plumbing — paths, ports, buffers, reconnects | 25 | **No.** Wrong → it breaks loudly. |
| Behavioral — changes a number a rule would read | 80 | see below |
| | **206** | |

The 80 behavioral, hand-classified one by one (the regex is not trusted for this;
the classes below sum to exactly 80):

| class | n | risk | why |
|---|---:|---|---|
| **Fit to returns** | **0** | — | **Nothing. There is no strategy layer.** |
| Measured vs *structure* | 8 | low | searched, but against event counts — never P&L |
| Reasoned, never searched | 13 | **none** | may be wrong; wrong ≠ overfit |
| Definitional / scope | 20 | none | declares what you look at, not how you judge |
| Backtest scope & policy | 7 | none-yet | unused; no engine calls them |
| Perf / payload | 11 | none | buffer sizes, bar counts, reconnects |
| Secrets & endpoints | 6 | none | `.env`, URLs |
| Plumbing (`_ROOT` paths) | 5 | none | |
| Cosmetic the regex missed | 5 | none | `chart.LAYERS`, the delta-strip colors and pane |
| Derived from others | 2 | none | `ma.ACTIVE`, `ribbon.PERIODS` |
| Cost assumptions | 2 | **special** | see §6 |
| The seal | 1 | **must never be tuned** | `SEALED_FROM` |
| | **80** | | |

**So the dials that actually shape a number a rule would read: 21** — the 8
measured plus the 13 reasoned. Out of 206 constants. Everything else is scope,
plumbing, paint, or a decision nobody has made yet.

### The 8 measured

| dial | value | fit against | by |
|---|---|---|---|
| `swing.RETRACE` | 3.0 | swing count & confirmation lag | `scale_ladder.py` |
| `range_scale.WINDOW_MINUTES` | 30 | error in *effective* retrace | `seasonality_report.py` |
| `session_stats.RECENT_WINDOW_MINUTES` | 30 | event count + 4N confirmation | `session_window_study.py` |
| `session_stats.RECENT_MIN_BARS` | 6 | same | same |
| `regime.ALIGN_TREND` | 0.60 | measured percentiles, 163k bars | `ribbon_regime.py` |
| `regime.WIDTH_TREND` | 5.0 | same | same |
| `regime.WIDTH_PINCH` | 2.0 | same (p10 of width) | same |
| `regime.CONFIRM_BARS` | 3 | chatter | same |

### The 13 reasoned but never searched

`absorption.MIN_ABS_DELTA` `MIN_VOLUME` `MIN_DELTA_RATIO` (all 0.0 — no
threshold at all) · `profile.BINS_PER_SCALE` = 8 · `session_stats.BINS_PER_SCALE`
= 8 · `range_scale.MIN_BARS` = 8 · `session_stats.HVN_MIN_SHARE` = 0.5 ·
`LVN_MAX_SHARE` = 0.15 · `ribbon.COUNT/START/STEP` = 32/5/5 ·
`profile.VALUE_AREA` = 0.7 (convention) · `profile.MAX_CLOSED` = 6.

**These carry zero overfitting risk, and that is not the same as being right.**
See §5.

---

## 5. What overfitting actually requires

Three ingredients. Remove any one and it cannot happen.

1. **A free parameter** — something you can change.
2. **A search** — trying more than one value.
3. **An objective computed from outcomes** — returns, P&L, hit rate.

This is why the taxonomy above is not pedantry. `HVN_MIN_SHARE = 0.5` might be a
bad number. Nobody searched it, so it cannot be overfit — it can only be
**wrong**, and wrong is *bias*, not *variance*:

| | bias (a wrong, unsearched number) | variance (a number fit to returns) |
|---|---|---|
| in-sample | looks bad | looks **great** |
| out-of-sample | looks equally bad | dies |
| when you find out | immediately | after you fund it |
| cost | cheap, honest | expensive, silent |

**A wrong constant announces itself everywhere, equally. An overfit constant
hides in exactly the place you look and appears in exactly the place you don't.**
That asymmetry is why 13 unmeasured dials are a smaller problem than 1 fit one.

### The flat-surface protection, and it is measured

`scale_ladder.py` found **H = 0.503** — swing count obeys the random-walk law, so
there is no scale at which this market is special and **no "true" RETRACE to
find**. `session_window_study.py` found the same for N: confirmation falls off
*smoothly* from N=3 to N=10, no elbow, no cliff.

That is not a disappointment, it is armour. **When the objective surface is flat,
there is nothing to overfit to.** A parameter with no sharp optimum cannot be
fit hard even by someone trying. The two dials that were searched hardest are the
two that were measured to have no peak — so both are declared design choices
sitting on a tradeoff, not discovered truths.

---

## 6. The two dangerous numbers nobody searched

```
backtest.SLIPPAGE_TICKS      = 1
backtest.COMMISSION_PER_SIDE = 2.0
```

These are not fit to returns. They **determine** returns. Optimism here is free
P&L in a backtest, and it is not overfitting — it is simply lying, which the
taxonomy above will never catch because no search occurs. They belong in their
own class and want tape-measured evidence before any result leans on them
(`orb_va/fills.py` measured slippage on 20 years — that is the standard to hold
them to).

Related, from `DATA_AUDIT.md` and not optional: the continuous series is
**back-adjusted**, so deep-history prices are synthetic. Stops and targets must
be point-distance, never absolute levels or percent returns
(`USE_POINT_DISTANCE = True`).

---

## 7. What the brain will cost — the forward count

The indicator layer is effectively unoverfittable **because nothing in it has
seen a P&L**. Every gram of risk arrives with the signal layer, which does not
exist yet.

An honest enumeration of a rule-based VPbreakout, from the design discussions:

| stage | free parameters |
|---|---|
| **arm** | compression threshold · efficiency-prior floor · travel-budget veto · range-percentile gate · decide-at bar index |
| **direction** | the bias rule (or: arm both and let bias size instead) |
| **trigger** | level choice (extreme / shelf / VAH-VAL) · trigger type (stop / close / acceptance / delta / retest) · acceptance threshold · delta threshold · compression→confirmation scaling |
| **manage** | stop placement (which HVN, how far behind) · target (which LVN) · timeout · failed-break re-entry |
| **size** | position size · daily loss limit |
| | **≈ 17, essentially all fit to returns** |

Against what sample:

```
817 explore sessions
  × the share that show the setup      <- ASSUMED a third. NOT MEASURED.
                                          The catalog can answer this exactly;
                                          it should, before anything is built.
  ≈ 270 events
  ÷ 17 free parameters                 ≈ 16 events per parameter
```

Sixteen is in the danger zone before you account for the fact that **sessions are
not independent** — volatility clusters, so effective N is lower still. And note
the shape of the problem: **the signal layer would add more return-fit parameters
than the entire indicator stack has dials of any kind** (17 against 21, and those
21 have never seen a P&L).

The "a third" is a guess and is load-bearing, which makes it the first thing the
interrogation should replace with a count.

### Why k-NN first

```
k-NN over the catalog:  1 parameter (k)  →  ~270 events per parameter
```

A **17× better ratio**, and it is the mechanized form of what is already being
done by hand — "what does this session remind me of." The argument is not that
k-NN is better. It is: **if k-NN finds nothing, a 17-parameter rule "finding"
something is almost certainly fitting noise.** One parameter is the cheapest
possible test of whether there is any signal there at all.

---

## 8. The parameters that are not in any file

The census above counts 206 constants. It does not count the ones that matter
most, because they have no name, no file, and no number:

- **Which sessions got looked at.** Two so far, both from the vault.
- **Which hypotheses were proposed, and revised.** In one conversation the
  "range expands *and* efficiency rises" discriminator was proposed on one
  session and falsified on the next — it fires on the trap and stays silent on
  the real break. **That is two fits at N = 2, recorded nowhere but a chat log.**
- **Which fields exist at all.** `session_stats` publishes 27. Each one was a
  choice to compute *that* rather than something else.
- **The recent/prior design itself** — chosen from reasoning about two sessions.

**These are researcher degrees of freedom, they are unlimited, they are free to
spend, and nothing counts them.** Every config dial is visible and auditable;
none of this is. It is the reason the seal exists, and the reason a workflow of
"look at a session, form a view, adjust" is the most dangerous tool in the
project — precisely because it is the most enjoyable one.

The mitigations, in order of how much they buy:

1. **The seal.** 817 explore / 395 sealed, cut at 2025-10-01, time-forward
   because volatility clusters and a random split would leak.
2. **The random picker.** `explore_session` draws uniformly and *cannot* return
   a sealed session. Left to choose, a person picks the memorable ones — a biased
   sample nothing records.
3. **The catalog.** 66,625 rows × 31 columns × 817 sessions. **Description is
   free**: looking at explore distributions costs zero degrees of freedom. Only
   *decisions* cost.
4. **Population questions over anecdotes.** "Does range expansion with rising
   efficiency separate breaks from traps" is a query over 66k rows, not an
   argument from three sessions.

---

## 9. The ledger — what is spent

| item | status |
|---|---|
| **Percentile-table leak** | **retired.** Two populations, separate files (`NQT_5m_full.npz`, `NQT_5m_explore.npz`), each stamped with `built_from` / `cutoff_utc` / `sessions_used`; every read names which it wants. They genuinely differ: NY bar 20, range 3.0× range_scale → 3.3rd percentile full vs 2.8th explore. |
| **N study** | **spent, mildly.** Used all 1,212 sessions before the seal existed. Fit to *event counts, not returns* — the vault informed it, but not through the channel that matters. Re-run explore-only before any sealed evaluation. |
| **Two sealed sessions eyeballed** | **spent.** 25 Jun '26 and 16 Jun '26. 2 of 395. |
| **The efficiency hypothesis** | **born from sealed data.** Not fatal — it inverts the flow rather than corrupting it, and explore is now the honest test *for that specific idea*. But the vault is no longer clean for it. |
| **Catalog** | clean by construction. Default build physically cannot write a sealed row; percentile fields are deliberately absent so the full table's provenance cannot leak in. |
| **The habit** | **the live risk.** The chart opens on recent bars; recent is sealed. The natural workflow pulls from the vault by default. Use the picker. |

### The order of operations, and why it is the whole point

Everything that costs **zero** degrees of freedom happens before anything that
costs one:

1. **Seal** — first, because it is the only step that gets worse every day it waits.
2. **Catalog** — description is free.
3. **Interrogate** — distributions, joint distributions. Reports, not rules. Still free.
4. **Only then, a signal** — k-NN before any rule system.

---

## 10. What does not exist yet

| | state |
|---|---|
| `src/strategy/` | **empty folder** |
| signals | none |
| risk | `config/risk.py` reserved by CLAUDE.md; no module |
| execution | `backtest/bracket.py` has the right shape (entry stop + SL/TP as absolute levels) and nothing calls it |
| `broker/orders.py` | **does not exist** — `broker/` is read-only: auth, accounts, contracts, history, market feed |
| `projectX_API/` docs | only the `account/` endpoint mapped; order/position endpoints unmapped |

Execution is genuinely greenfield, and that is correct — it is the *last* thing
needed. The order that matters: understand the population, find whether a signal
exists at one parameter, and only then decide what to send anywhere.

---

## Cross-references

| doc | job |
|---|---|
| `FIELDS.md` | generated — every field, a section per indicator |
| `FIELDS_V2.md` | generated — the same contract as one table |
| `ARCHITECTURE.md` | the code map: folder tree and who-imports-who |
| `src/session_history/README.md` | the seal, the catalog, the debts |
| `SESSION_SPLIT.json` | the frozen receipt: which sessions are sealed |
| `DATA_AUDIT.md` | data truth: gaps, back-adjustment, bar stamping |
| `CLAUDE.md` | the rules (not part of "the mds") |
