# SESSION_STATS.md — the card, and every dial behind it

**This one indicator is the strategy.** Everything VPbreakout reads to judge a
session lives here: 27 fields, one row per bar, from the first bar of London or
NY to now. No other indicator is wired into it — `regime`, `swing`, `legs`,
`breaks`, `ribbon` and `ma` are all deliberately *not* dependencies.

Hand-written, like `FIELDS_V3.md` and unlike `FIELDS.md` / `FIELDS_V2.md`, which
are generated across all twelve indicators. This is the strategy's own reference:
what each number means, what it costs in degrees of freedom, and where it has
already lied.

```
code    src/indicators/session_stats.py          (27 fields)
dials   src/config/indicators/session_stats.py   (6 of its own)
deps    sessions -> range_scale -> session_stats
```

---

## 1. See it

```
commands.bat -> Chart -> STUDY a random session       # serves AND opens on it
commands.bat -> Chart -> Snapshot table - session card only
```

or, directly:

```powershell
python -m src.cli.chart --study London        # serve, pick, open - one command
python -m src.cli.table --group session_stats # this block and nothing else
```

`--study` picks uniformly from the **explore** side and cannot return a sealed
session. Naming one is optional (`--study NY`). It deep-links the chart
(`/?symbol=..&tf=..&at=<epoch>`) so there is no timestamp to retype — the tool
that knows the moment navigates to it.

`--group session_stats` shows the 22 non-detail fields plus the 6 bar columns
(time, OHLC, volume) and hides the other eleven indicators entirely. **Ctrl+C**
copies the selected rows as a markdown table with a context line and raw field
keys — the paste-to-an-analyst loop.

Two other ways to read the same numbers:

| surface | what it is |
|---|---|
| the session panel | the card as one instant, on the chart — click the chart |
| the catalog | the card as a population: 66,625 rows × 817 explore sessions, `cache/session_history/catalog_NQT_5m_explore.parquet` |

The card in the panel and the row in the table are **the same computation** —
both subscribe to one server-side row. They cannot disagree.

---

## 2. The 27 fields, by job

### Shape — what this session looks like as one candle (7)

| field | unit | means |
|---|---|---|
| `session_range` | × range_scale | `(high − low) / range_scale`, so far |
| `session_bars` | count | bars since the open |
| `session_net` | × range_scale | `(close − open) / range_scale`. Signed |
| `session_net_ratio` | −1..+1 | `net / range` — direction and strength in one number |
| `session_closed_ratio` | 0..1 | `(close − low) / range` — where price sits in its own range now |
| `session_high_at_ratio` | 0..1 | how far into the session the high was set. **Near 0 = made early and defended** |
| `session_low_at_ratio` | 0..1 | the same, for the low |

**No body/wick split, on purpose.** Given `net_ratio` and `closed_ratio`,
`open_ratio = closed_ratio − net_ratio` *always*, and body/up-wick/low-wick are
arithmetic on those two. Publishing them would be the same two facts told three
extra times.

`high_at_ratio` is **the only forward-looking field on the card.** Everything
else describes what already happened; the *time* an extreme formed constrains the
rest of the day and is known early.

### Phase — the actual signal (5)

Two sliding windows: `recent` (the last `RECENT_WINDOW_MINUTES`) and `prior`
(the same width immediately before it). Recomputed every bar. **Sliding, never
tumbling** — a fixed non-overlapping block reintroduces the blending bug at an
arbitrary cut point.

| field | unit | means |
|---|---|---|
| `session_efficiency_recent` | 0..1 | `range / travel` in the recent window. 1.0 is a straight line; small is chop |
| `session_efficiency_prior` | 0..1 | the same, one window back |
| `session_range_ratio` | ratio | recent span ÷ prior span. **≪ 1 is contraction — a base forming** |
| `session_volume_ratio` | ratio | recent volume ÷ prior volume |
| `session_dir_change_rate` | 0..1 | close-to-close reversals in the recent window ÷ its bars |

**Why these exist at all.** They replaced `session_efficiency`,
`session_dir_changes` and `session_travel`, which were computed open-to-now and
*silently failed* on any session with two characters. A real crash-then-base
session read `efficiency 0.33` — the blend of a ~1.0 impulse and a ~0.1 base,
describing neither. Aggregates over a bimodal session do not error. They return
a plausible number pointing the wrong way.

`dir_change_rate` is a **rate, not a count**, and that is a second bug fixed: a
monotonic count can only ever grow, so it can never report that the market *just
started* trending.

**These need no range_scale.** A ratio of two windows of the same unit cancels
it — normalising twice would solve a problem that does not exist.

### The signature the strategy hunts

```
efficiency_prior   high      the impulse
efficiency_recent  low       handing off to
range_ratio        << 1        a base
volume_ratio       < 1         drying up
```

### Flow — NQT only (2)

| field | unit | means |
|---|---|---|
| `session_volume` | contracts | total since the open. **Unsigned, so cumulative is honest here** |
| `session_delta_recent` | contracts, signed | buys − sells over the recent window, **never since the open** |

**Why delta is windowed and volume is not.** A cumulative sum of a *signed*
quantity across regimes does not average them, it **cancels** them. A real
session: 211K volume, a genuine crash, genuine dip-buying, net delta **−3K** —
which reads as "no conviction" when conviction happened twice, in opposite
directions. Volume has no such problem: "566K traded" stays true however the
session turned.

### Levels — for stops and targets, not entries (6)

| field | unit | means |
|---|---|---|
| `session_poc` | price | the single price with the most volume traded at it |
| `session_poc_ratio` | 0..1 | `(poc − low) / range` — where fair value sits inside the range built to find it |
| `session_val` / `session_vah` | price | the value area: the band around the POC holding `profile.VALUE_AREA` of volume |
| `session_hvn` * | prices | other volume peaks ≥ `HVN_MIN_SHARE` of the POC's. **A stop belongs BEHIND one** |
| `session_lvn` * | prices | volume troughs ≤ `LVN_MAX_SHARE` of the POC's. **A target** — price that reaches one keeps going |
| `session_bins` * | histogram | the raw profile. The chart draws it; nothing else should read it |

\* detail — a list, not a single fact. Click **Details** in the table.

**The entry is not the tick extreme.** That is where resting stops cluster and is
the wick you get filled on before the reversal. The trigger belongs beyond the
volume *shelf*; the stop behind the HVN that should hold if the break is real.

### Versus history — the un-confounding layer (4)

| field | unit | means |
|---|---|---|
| `session_range_percentile` | 0..1 | where `session_range` ranks against history **at the same elapsed bar of the same session name** |
| `session_travel_percentile` | 0..1 | the same, for cumulative travel |
| `session_volume_percentile` | 0..1 | the same, for cumulative volume |
| `session_travel_budget` | ratio | travel so far ÷ a typical full session's travel. **Past 1.0 the day has already spent its move** |

**Why percentile and not points, and not even ×range_scale.** `range_scale`
corrects for the regime the market is in *now*. It does not correct for whether
the distribution it is drawn from has itself drifted across the dataset. A rank
against the same dataset's history at the same elapsed bar sidesteps both: a
number is not big or small in the abstract, only relative to what usually happens
by this point in a London or NY session.

These are also the answer to `volume_ratio`'s **clock confound** (§5).

### Detail (2)

`session_from_time` / `session_to_time` — where the profile drawing anchors.

---

## 3. What is None, and when

The card refuses rather than guesses. Every None is a designed refusal.

| condition | what goes None |
|---|---|
| session is not London or NY | **everything** — the halt and Asia publish nothing at all |
| `range_scale` not warm (< `MIN_BARS` = 8 bars) | `session_range`, `session_net`, the profile, the percentiles |
| fewer than `RECENT_MIN_BARS` = 6 bars | the whole phase block, `delta_recent` |
| bar file, not tick-rebuilt (NQ/ES, not NQT) | `session_volume`, `session_delta_recent`, `session_volume_percentile` |
| no volume-at-price (`python -m src.cli.vap`) | `poc`, `poc_ratio`, `val`, `vah`, `hvn`, `lvn`, `bins` |
| the chart's Profile toggle is off | the same profile fields — a plain browse does not pay for VAP unasked |
| no session-history table built | the four history fields |
| session has run deeper than any in history | `*_percentile` for those bars |

**A None is never a zero.** A fabricated 0 delta would claim buying and selling
were balanced; a fabricated 0 percentile would claim today is the quietest
session ever recorded. `tests/test_fields.py` enforces that every field declares
its unit, and the indicator declares `Unavailable` rather than proxy a value.

---

## 4. The dials — 14 reach this card

### Its own (6) — `src/config/indicators/session_stats.py`

| dial | value | class | why that value |
|---|---|---|---|
| `RECENT_WINDOW_MINUTES` | 30 | **measured** | `session_window_study.py` over 1,212 sessions: N=6 bars sits near peak event count while still confirming a real plurality against its own 4N companion. Falloff is smooth — no elbow, no cliff |
| `RECENT_MIN_BARS` | 6 | **measured** | same study; on 5m bars, 30 minutes *is* 6 bars |
| `TRACKED_SESSIONS` | London, NY | scope | VPbreakout trades these. Asia and the halt publish nothing — a "session so far" nobody asked for is a number a rule could accidentally read |
| `BINS_PER_SCALE` | 8 | reasoned | ~one bin per eighth of a typical bar → 30–60 bins per profile. Independent of `profile.py`'s own dial: a session spans hours, a leg spans bars |
| `HVN_MIN_SHARE` | 0.5 | reasoned | "half as loud as fair price" — loud enough that a stop rests on real acceptance, not a one-bin wobble |
| `LVN_MAX_SHARE` | 0.15 | reasoned | well below "unremarkable" rather than merely "less than the peak" |

### Inherited (8) — change these and the card's numbers change

| dial | value | from | touches |
|---|---|---|---|
| `range_scale.WINDOW_MINUTES` | 30 | `range_scale` | **measured**. `session_range`, `session_net`, every bin width |
| `range_scale.MIN_BARS` | 8 | `range_scale` | reasoned. Also gates whether the card publishes at all |
| `profile.VALUE_AREA` | 0.7 | `profile` | convention (standard market profile). `session_val` / `session_vah` |
| `profile.BASE_TIMEFRAME` | 30s | `profile` | scope — the VAP grid the profile folds |
| `session.SESSIONS` | London 03:00–08:00 ET, NY 08:00–17:00 ET | `session` | definitional — when a session starts, so every "so far" |
| `session.SESSION_END_INCLUSIVE` | True | `session` | definitional — bars are close-stamped, so `start < t <= end` |
| `session_history.PERCENTILES` | 0..100 by 5 | `session_history` | resolution of the four history fields |
| `session_history.SEALED_FROM` | 2025-10-01 | `session_history` | **the seal.** Never tune |

### The count that matters

| | n |
|---|---:|
| Dials that shape a number on this card | **14** |
| — measured (against **event counts**, never P&L) | 3 |
| — reasoned, never searched | 5 |
| — scope / definitional | 4 |
| — infrastructure (resolution, the seal) | 2 |
| **Fit to returns** | **0** |

**Nothing here has ever seen a P&L.** Overfitting needs a free parameter, a
search, *and* an objective made of outcomes. The third is missing entirely, so
the card cannot currently be overfit — only be *wrong*, which is bias: it shows
up equally in and out of sample, and announces itself honestly.

The 5 reasoned dials are the ones most likely to be simply wrong.
`HVN_MIN_SHARE = 0.5` and `LVN_MAX_SHARE = 0.15` in particular were never
measured against anything — they are stop and target placement, so they are worth
measuring against the catalog before a rule leans on them.

**A signal layer would add ~17 more, essentially all fit to returns** — more than
this card's entire dial surface, against ~270 setup-sessions. See `FIELDS_V3.md`
§7.

---

## 5. Where the card has already lied

Hard-won, from real sessions. Every one of these is a live limitation, not
history.

### `volume_ratio` is confounded with the clock

On NY 16 Jun '26 it peaked at **6.38** at 13:35 UTC — five minutes after the cash
open. That surge happens **every day regardless of the market**, because the
prior window is pre-open and the recent window is post-open. The two-window
comparison assumes the prior window is a fair baseline for the recent one, and
across the cash open it simply is not.

`session_volume_percentile` is the un-confounded version: it compares against the
*same elapsed bar of other sessions*. **Prefer it.** Whether the spike is
universal is a one-query check over the catalog and has not been run.

### Range expansion alone is not a breakout

Same session, two bars with near-identical range expansion:

| | `range_ratio` | `eff_recent` | `eff_prior` | what it was |
|---|---:|---:|---:|---|
| 13:55 | 2.15 | 0.38 | 0.39 | **trap** — range up, efficiency flat. 280 pts *against* within 40 min |
| 14:35 | 2.45 | 0.57 | 0.28 | **real** — range up, efficiency doubled |

Range expanded identically. Only efficiency separated them. **The pair is the
discriminator; neither number works alone.** Expansion with flat efficiency is a
volatility explosion with no direction in it — which is what a trap is made of.

### …but the efficiency pair is confirmation, not a trigger

The same session's actual break was **14:20** — the bar that closed 45 points
*below* the base with an 11% wick, four bars before price ran 234 points. At
14:20 `eff_recent 0.42` vs `eff_prior 0.41`: **flat**, and `volume_ratio 0.85`:
*contracting*. The efficiency pair says nothing. It only confirms at 14:25 and
peaks at 14:35 — one to three bars and 60–140 points late.

Meanwhile the *failed* break at 13:35 (`eff_recent 0.44` > `eff_prior 0.35`,
`range_ratio 1.74`) satisfies the rule and lost money.

**So: the phase fields are good at reading what a session has been and bad at
saying what to do next.** The thing that actually separated the two breaks was
boring — *did the bar close outside the range, or just poke through it?* Which is
what `breaks.py`'s `USE_CLOSE = True` has always encoded: a wick through a level
that closes back inside is a rejection, not a break.

### The card cannot tell continuation from breakout

On that same session `high_at_ratio` was **0.06** and `net_ratio` was negative
from the first bar. Under one reading the 12:30–13:30 "base" was a coil that
resolved. Under another it was a *pause inside an established downtrend*, and
14:20 was continuation, not breakout. Those want different stops and different
targets, and nothing on the card distinguishes them.

### The window still blends, one scale down

`RECENT_WINDOW_MINUTES = 30` is 6 bars on 5m. If a move is 3 bars old, the recent
window still contains half of what preceded it. `delta_recent 17` during a
breakout is not "no buying" — it may be buying netted against the base before it.
The blending bug, at smaller scale.

---

## 6. What is missing before this is a signal

| | state |
|---|---|
| the trigger | undecided. Five candidates: resting stop / bar close / **acceptance** (volume beyond the shelf) / **delta confirmation** / retest |
| the frozen range | **absent.** The card is open-to-now, so "price broke the range" is true by definition on every new extreme. A breakout needs a reference range that *stops updating* |
| the bias | untested. Arming one side means being absent for the move when wrong — it must beat the base rate by enough to pay for every opposite break sat out |
| the failed-break trigger | absent, and it fires exactly on the days the breakout side loses |
| `src/strategy/` | an empty folder |

---

## Cross-references

| doc | job |
|---|---|
| `FIELDS_V3.md` | the whole system + the full 206-constant parameter audit |
| `FIELDS.md` / `FIELDS_V2.md` | generated — all 12 indicators, all 76 fields |
| `src/session_history/README.md` | the seal, the catalog, the known debts |
| `SESSION_STATS_BRIEF.md` | the design brief that produced the two-window rework |
| `src/indicators/session_stats.py` | the code. Its module docstring is the long-form of this file |
