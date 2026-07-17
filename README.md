# algo_3

Algorithmic trading project (ProjectX / TopstepX) — Python, CLI-first.

## Setup

```powershell
# 1. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the env template and fill in your keys
copy .env.example .env
```

## Run

Launch the command menu (double-click or run from a shell):

```
commands.bat
```

Or run a door directly:

```
python -m src.cli.data NQ 5m       # load & summarize prepared bars
python -m src.cli.chart --open    # replay chart at http://127.0.0.1:8765
python -m src.cli.capture --seconds 60   # record the live TopstepX market feed
```

## Chart

`python -m src.cli.chart` serves a dark, gridless candle chart of the NQ/ES Parquet
store at **http://127.0.0.1:8765**. Browse any timeframe, or hit **Replay**, click a
bar to cut back to that moment, and step forward one bar at a time (play/pause,
1x/2x/4x, `Space` and `→`). Zoom and pan stay free the whole time. Switching
timeframe keeps your place — it reloads the new bar size centred on the window you
were viewing, at the same zoom, instead of jumping to the latest bars.

It stays fast by never sending a dataset it does not need: bars are packed into a
flat 24-byte record file that the server memmaps and slices, they cross the wire as
raw bytes rather than JSON, and the browser holds a bounded window (~5,000 bars) that
trims behind. A 6-million-bar 1m dataset opens as one small fetch.

**Replay runs on the server.** It owns the cursor, the clock, and the live indicator
state, and publishes one snapshot per bar over a stream the chart subscribes to. Seeking
back replays the warmup silently, so the indicators at a cut point hold exactly what they
would have held had you played into it — nothing can see past the cursor, by construction.

`NQT` bars carry **order flow**: delta (aggressive buys minus aggressive sells) is drawn as
a signed strip beneath the price, green above the zero line and red below. Bars that closed
*against* their own flow — **absorption**, 21.1% of them — are published as a field and shown
in the table. Their chart markers are off by default (`DRAW_MARKERS`): a dot on one bar in
five is noise on the candles. The NT8 `NQ`/`ES`
bars have no aggressor recorded, so the strip is simply empty for them — never a flat zero,
which would claim the buying and selling were balanced.

**Structure** is drawn in three layers, and they are told apart by *shape*, not by colour.
A blue **dot** sits on the bar that made each confirmed swing. A muted green or red
**line** runs from that swing to the next one — one straight stroke, not a claim about the
path, since the candles under it already say what price did. Over both, a **break of
structure**: when a bar *closes* through a standing swing level, a bright **dashed** line
runs from the swing that set the level, along it, to the close that took it out. Green when
a swing high goes, red when a swing low does. A level fires once and is spent.

A leg and a break are both a red or green line, so hue cannot also carry which-is-which.
The dash does: solid is context, dashed is the event. All of it lives in
`config/indicators/{swing,legs,breaks}.py` — the frontend draws four shapes and knows what
none of them mean.

A swing is confirmed only once price has retraced `RETRACE x range_scale` from the extreme
— so the structure appears late, drawn from the bar that *proved* the turn back to the bar
that *made* it. Nothing else is honest: a high does not announce itself. (A wick through a
level that closes back below it is a rejection, not a break; set `USE_CLOSE = False` in
`config/indicators/breaks.py` to measure the difference.)

That threshold is measured in **multiples of the current typical bar range**
(`src/indicators/range_scale.py`), never in points. NQ's median 30s range moved between
4.50 and 14.25 points across 29 months, so a fixed point threshold is correct for one
volatility regime and silently wrong for the next. Measured in units of itself, "a real
pullback" means the same thing in a quiet August and in April 2025 — multiply every price
in the data by ten and the identical swings are found.

**The moving-average ribbon** is a fan of 32 simple moving averages of the close, periods 5
through 160 (`config/indicators/ribbon.py`). Each line is coloured by its *own* slope — green
where it rose from the previous bar, red where it fell — so a clean trend reads as a fan of
one colour and a turn shows the fan changing colour from the short end inward. A line
publishes nothing until it has its full period of closes; it never stands a short average in
for a long one. It reuses the same **segment** shape the legs and breaks already draw, so it
added no frontend at all, and it is one Layers toggle ("MA ribbon") like every other drawing.

**Named moving averages** (`src/indicators/ma.py`, `config/indicators/ma.py`) are a short,
explicit list — "the 50", or "the 50 and the 200" — each independently switched on or off and
drawn in its own fixed colour, unlike the ribbon's fan which is coloured by slope. Add a line
by adding an entry to `LINES` in config; no change to the indicator or the chart is needed
either way, since it reuses the same **segment** shape the ribbon and legs already draw. It
ships with the 50-period line on. One Layers toggle ("Moving averages") like every other
drawing.

**Regime** reads the ribbon's shape (`src/indicators/regime.py`). The 32 lines collapse to three
dimensionless numbers — **alignment** (are the lines stacked in period order? +1 a clean
up-trend, −1 down, 0 a scrambled fan — the sortedness of the permutation), **agreement** (are
they all sloping the same way this bar? it turns before alignment does), and **width** (how
flared the fan is, in `range_scale`, which by the `(N−1)/2` lag geometry is proportional to
price velocity). From those it labels each bar **up / down** (stacked *and* flared),
**transition** (the fan pinched shut — a coiled squeeze), or **chop**. On the chart it draws
two things on the one "Regime" layer: a dashed rule where the regime turns, and a faint
background tint on every warm bar (`BAND_COLORS`), so runs of one regime read as continuous
shaded bands behind the candles. A new label must hold `CONFIRM_BARS` before it is adopted, so it
does not chatter. The cutoffs are measured, not guessed — on 163k NQT 5m bars the tape runs
~30% trend, ~60% chop, ~10% squeeze, median regime 17 bars (`scratch/analysis/ribbon_regime.py`
prints the distributions; run it from `commands.bat` → Analysis → Calibration). The three
readings ride the snapshot table whether or not the rule is drawn.

**The volume profile** is the toolbar's rightmost control. It covers the **developing
range** — from the last confirmed swing to the current bar. It grows every bar, never looks
ahead, and always exists, including right after a break of structure, when there is no
complete high-low box at all.

When a swing confirms, that profile **freezes onto the range it described** and a new one
begins. So the chart carries a row of profiles, one per structure, each anchored to its own
span, dimmed behind the live one. The last six are kept.

Each bin is coloured by who crossed the spread; the amber line is the point of control and
the faint pair around it is the value area. Bins are sized in `range_scale`, never in
points — otherwise the histogram would be drawing the clock, four times spikier overnight
than at the New York open.

**What the profile says**, as opposed to where its levels sit, is five readings, and the
table shows those rather than the raw prices:

| reading | what it means |
|---|---|
| `value_width` | `(VAH − VAL) / range_scale`. Narrow is balance; wide is a market trading away from itself. Median 4.25, p95 14.13 |
| `poc_position` | where value sits inside the range price covered, 0 at the low to 1 at the high |
| `poc_distance` | `(close − POC) / range_scale`. How far price is from the fair one |
| `price_vs_value` | above / inside / below the value area — the market accepting the price it built, or not |
| `delta_at_poc` | who crossed the spread to build the fair price |

**The session scorecard** (`src/indicators/session_stats.py`) is the running measurement
behind the planned **VPbreakout** strategy — everything it needs to judge a London or NY
session's character, live, from the session's own first bar to now. Asia and the
maintenance halt are out of scope (`config/indicators/session_stats.py` `TRACKED_SESSIONS`)
and publish nothing at all: a "session so far" for a session nobody intends to trade would
only invite a rule to accidentally read it.

It treats the whole session as one candle — `session_range` is its high minus its low,
`session_net` is close minus open. There is no body/wick split: given `session_net_ratio` and
`session_closed_ratio`, `open_ratio = closed_ratio - net_ratio` always, so body/up-wick/
low-wick would be three lines of arithmetic on two numbers already on the card, not a third
fact — provable, not a judgment call. Like everything else in the structure layer,
`session_range` and `session_net` are measured in multiples of `range_scale`, never raw points
— a session that is "big" in April must not silently mean something different in August. The
ratio fields need no such conversion; they are already a fraction of the session's own range.

**`session_efficiency`/`session_dir_changes`/`session_travel` do not exist.** They used to be
cumulative since the session opened, and that silently blended any session with more than one
character into a number describing neither — measured directly on the real crash-then-base NY
session of 25 Jun '26, cumulative efficiency never exceeded ~0.5 all session, hiding a crash
that was briefly running near 1.0. Replaced by a sliding **recent-vs-prior window pair**:
`session_efficiency_recent` / `session_efficiency_prior` (range/travel over the last
`RECENT_WINDOW_MINUTES`, and the same window immediately before it), `session_range_ratio` and
`session_volume_ratio` (recent ÷ prior — contraction reads `<< 1`, the classic base-forming
tell), and `session_dir_change_rate` — a RATE over the recent window, not the monotonic count
`session_dir_changes` was, which could only ever grow and so could never report that the market
had just started trending. None of these need `range_scale`: a ratio between two windows of the
same unit cancels it, exactly the way `session_net_ratio` already does for the whole session —
normalizing twice would solve a problem range_scale already solved. `N` (30 minutes / 6 bars on
5m) was measured, not guessed: `scratch/session_research/session_window_study.py` walks all 1,212
London/NY sessions in the dataset and picks the window by event count and how many transitions
each candidate's own 4N companion confirms nearby — the same method `scale_ladder.py` uses for
`RETRACE`, and it finds the same thing: no privileged scale, confirmation falls off smoothly
with no elbow, so this is a considered point on a tradeoff, not "the true N." Deliberately not
coupled to `indicators/regime.py` — not considered complete or validated.

`session_high_at_ratio` / `session_low_at_ratio` say how far
into the session each running extreme was set. `session_volume` needs order flow and stays
cumulative since open — unsigned and genuinely additive, so a running total is honest.
`session_delta_recent` needs it too but is deliberately NOT cumulative: delta is signed, and a
running sum across a session that changed character doesn't average opposing regimes, it
cancels them — real selling in a crash, netted against real buying in the bounce that followed,
reads as indecision when neither was. It sums only the last `RECENT_WINDOW_MINUTES` instead.
`session_poc` needs volume at price — None on a bar file, same honesty `orderflow` and
`profile` already keep — and folds into the same live tick-grid accumulator (`Ladder`, now in
`src/profile/store.py`) that `profile.py`'s developing range uses, so both indicators share one
fold instead of two.

**`session_hvn` / `session_lvn`** find the profile's OTHER shelves and gaps, besides the POC —
a strict local peak or trough among filled neighbour bins, carrying at least `HVN_MIN_SHARE` (a
real shelf, not a one-bin wobble) or at most `LVN_MAX_SHARE` of the POC's own volume (a real
gap, not an ordinary thin bin). These are for **stop and target placement, not entry**: an HVN
is what a stop belongs *behind* — real acceptance rarely gives way to noise — and an LVN is a
target, because price that reaches one tends to keep moving through it fast. Neither is the
session's tick extreme, which is only where resting stops cluster. One real limitation:
`store.rebin()` drops zero-volume bins entirely, so a true empty gap — arguably the strongest
possible LVN — is invisible to this list rather than found by it.

Unlike `profile_val`/`profile_vah` (hidden behind **Details** in the desktop table),
**`session_val`/`session_vah` are shown facts**, not buried: entry and stop placement read them
directly, so hiding them by default was the wrong call for this specific pair.
`session_hvn`/`session_lvn` stay `DETAIL` like `session_bins` does — they're lists of prices,
not a single reading.

**`session_range_percentile` / `session_travel_percentile` / `session_volume_percentile` /
`session_travel_budget`** place today's cumulative reading against *history at the same
elapsed bar of the same session name* — not points, and not even x-`range_scale` alone.
`range_scale` corrects for the regime the market is in *right now*; it does not correct for
whether the distribution `range_scale` is measured against has itself drifted over the life of
the dataset. A percentile rank against the same dataset's history sidesteps that: a number
isn't "big" or "small" in the abstract, only relative to what usually happens by this point in
a London or NY session. `session_travel_budget` is the fuel-gauge version of the same idea —
travel so far ÷ a *typical* (median) full session's travel; past 1.0 the session has already
covered more ground than an average day covers start to finish, which is exactly the question
"does a late break have anything left to spend" is asking.

These need `src/session_history`'s cached table (`python -m src.cli.session_history --symbol
NQT --timeframe 5m`, ~3s on the shipped dataset — 598 London + 609 NY sessions) **and** to be
told which symbol/timeframe to read it for. `session_stats` is the *one* indicator in this
codebase with a `symbol`/`timeframe` constructor argument for exactly that reason — every other
indicator is dataset-agnostic (`profile` reads volume-at-price off the event, never looks it up
itself), and this is the one exception, threaded from `chart.overlays.build_registry`.
`session_history/build.py` walks every session with `range_scale` flowing *continuously* across
session boundaries — it's a rolling window over calendar time, not a session-scoped one — and
reduces cumulative range/travel/volume per elapsed bar to percentile breakpoints, the same
segmentation helper (`indicators.sessions.session_runs`) `scratch/analysis/
session_window_study.py` uses.

**Click the current session's own dashed line** (London or NY) to open a live scorecard in
the top-right corner — the numbers update on every bar for as long as replay keeps running,
reading the same `snapshot.fields` the desktop table already receives
(`frontend/chart/js/session_panel.js`). Click the same line again to close it. Because
session_stats keeps no history of past sessions, only the *current* session's line is ever a
meaningful click target.

**The session also carries its own volume profile**, anchored the session's own open to now
— `session_poc`/`session_val`/`session_vah`/`session_bins`, drawn on the chart exactly the way
the developing swing-to-swing profile is (same `_histogram` helper, reused with its own
`source`/`layer` so the two profiles never collide or replace each other), one Layers toggle
("Session profile"). Volume at price is a per-bar store lookup, so it has its own toolbar
switch — **"Session profile: on/off"**, independent of the swing profile's own **"Profile:
on/off"**. Either can run without the other: turn the session one on and the swing one off to
watch only the session's profile, and vice versa, and neither pays for the other's fetch
(`chart.overlays.wants_vap`). The one asymmetry: if the swing profile is already paying for
the fetch, the session profile rides along on the same bars for free even with its own switch
off — there is no second fetch to skip, though the Layers checkbox still controls whether it's
actually drawn. Everything else on the card (range, net, travel, direction changes…) needs no
volume at price and keeps working regardless of either toggle.

`delta_at_poc` is the one almost nothing else can compute: it needs volume at price **and**
aggressor side, and both live only in the ticks. It sits near zero by construction — the
point of control is where buyers and sellers *agree* — so the tail is the signal, not the
centre. `|delta_at_poc| > 0.10` on 1.0% of bars.

Volume at price lives only in the ticks: a bar records its total volume, its high and its
low, never where between them the contracts changed hands. So it is folded once into a
packed store (`python -m src.cli.vap`, ~80s, git-ignored) at one timeframe — 30s. The
control is **disabled** rather than offered and quietly drawing nothing, on two counts: a
symbol with no ticks, and a timeframe the store cannot answer. A 15s bar cannot be sliced
out of a 30s store (the first half of every 30s traded at no price it knows), and a 45s bar
would be handed volume from the bars either side. 30s and every whole multiple of it work.

**Layers** in the toolbar hides any drawing you don't want to look at. It is a *visibility*
switch and never a compute switch: the server still computes every indicator and still
ships every mark, so a hidden leg is still a leg in the snapshot table, and the two windows
cannot drift apart about what happened — only about what is on screen. Toggling one back on
redraws the history it already accumulated, with no round trip. The session rules are
shown by default (`LAYERS` in `config/chart.py`) — a dashed vertical at each Asia/London/NY
**open and close**, on every symbol. The close sits on the session's last bar, so a session's
end and the next one's open are one bar apart, except the NY close (17:00 ET), which stands
alone before the maintenance halt. Closes are dimmer, with the label a notch lower; toggle
the whole layer off if it is more ink than you want, since the time axis carries the same fact. A layer whose indicator is switched off in config is
not offered at all, rather than offered as a checkbox that toggles nothing.

The chart draws; it does not compute. Indicators are computed once in Python and arrive
over `/api/overlays` as drawing instructions — a dashed, labelled rule at each
trading-session open (Asia / London / NY), and dots at the swings. Both are shapes the
frontend renders without knowing what a session or a swing is. The profile added no
frontend at all: a histogram bin is a segment, and that shape already existed.
Because the overlay request carries only the bars replay has revealed, a drawing can never
leak the future. See `BUILD_PLAN.md` for the road from here.

Editing HTML/CSS/JS? Just refresh the page. Editing Python? Add `--reload` and the server
restarts itself — replay sessions live in memory, so a restart retires them, and the chart
notices and silently re-seeds at the bar it had reached rather than reconnecting forever to
a session that no longer exists.

## Snapshot table

`python -m src.cli.table` opens a desktop window showing every replay snapshot as a row —
the bar, plus each indicator field, colour-coded. It **attaches to the replay the chart is
already driving**, so the drawings and the numbers move together and cannot disagree: there
is one cursor and one computation on the server, and both windows are subscribers.

It never wraps. Columns clip and the view scrolls horizontally. It follows the newest row
until you scroll up, then stays where you put it and counts what has landed; click **Follow**
(or scroll back to the bottom) to resume.

### One block at a time

Thirteen indicators publish a column each per field, which is a lot of table to hunt one
block through. `--group` narrows it to the blocks you name:

```
python -m src.cli.table --group session_stats          # the session card, alone
python -m src.cli.table --group session_stats,profile  # repeat or comma-separate
```

The **bar** columns always survive — they are the time and price every other number is
located against. The window titles itself with the filter, so a narrowed table and a full
one are told apart at a glance, and the filter holds when the chart retires one replay for
another.

### Copying rows out

Select rows and press **Ctrl+C** (or click **Copy**). They land on the clipboard as a
markdown table, with a context line naming the symbol, rung and session — so a row that
looks wrong can be pasted into a chat or an issue and still say what it said, which a
screenshot cannot. It copies the columns **as shown**, filter and **Details** included, and
uses raw field keys (`session_efficiency_recent`, not the header's shortened `efficiency
recent`) because
those are what [`FIELDS.md`](FIELDS.md) defines.

### Three scales at once

A replay publishes a row per **rung** of its ladder — `30s`, `3m`, `15m` (`LADDER` in
`config/replay.py`). Each rung folds the base bars into a coarser one and runs its **own**
indicator state over it, so the same code says something different, and equally true, at
each scale. That is what "the indicators are scale-free" means when you can look at it: a
swing is `RETRACE x range_scale`, and `range_scale` is measured from the bars in front of it.

```
python -m src.cli.table --rung 30s     # three windows, one cursor
python -m src.cli.table --rung 3m
python -m src.cli.table --rung 15m
```

**They cannot drift apart.** These are three filters over one stream, not three replays: a
15m bar closes on the exact base bar that completes it, so its row lands on the same tick of
the clock as the thirtieth 30s row. Alignment is arithmetic, not coordination. A rung whose
bar is still forming publishes nothing at all — a bar that has not closed has no close — and
a rung's bar is, to the tick, the bar the store itself would have built.

The chart draws one timeframe and ignores the other rungs' rows; a 15m bar appended to a 30s
series would be a bar out of order. The ladder is why three tables cost one warmup.

Only whole multiples of the base timeframe become rungs: 30s folds into 3m and 15m exactly.
A 2m base gets no 3m rung, because two thirds of a bar is not a bar.

Columns are not configured anywhere: the first six describe the bar, the rest are whatever
fields the session publishes, **grouped under the indicator that published them**. Add an
indicator and a block appears. A field never repeats its own group's name — `sessions` over
`session`, or `profile` over `profile_poc`, says one thing twice — so the prefix is stripped,
and where nothing is left the group name *is* the column's name.

**Every column says where it came from.** Each block is tinted with its indicator's own
hue, a hairline marks the seam between blocks, and a legend along the bottom names them.
The colour rides the *header*, never a cell — a cell's colour already means green-up,
red-down, grey-absent, and two meanings on one pixel is one meaning too many.

**Hover any column header** and it tells you which indicator owns it, what unit the number
is in, and what it means. `price`, `points` and `x range_scale` look identical in a table
and behave completely differently when the market changes — the unit comes first.

The same text, for every field, is **`FIELDS.md`** — a section per indicator, with the source
and config files it lives in — and **`FIELDS_V2.md`**, the same contract as one flat table,
every field in a row carrying the indicator that owns it. Both are generated by `python -m
src.cli.fields --write` from definitions that live beside the code that computes each number,
so they cannot disagree. A test fails if a field has no definition, if its unit is
unrecognised, if the two documents describe different fields, or if either goes stale.

**`FIELDS_V3.md`** is the third and is not generated, because what it says is not
derivable from the registry: how the menu, the fields and the surfaces are wired, and
which of the project's 206 config constants could ever be overfit. The short answer is
that 21 shape a number a rule would read and **none has ever seen a P&L** — every gram
of that risk arrives with the signal layer, which does not exist yet.

The row is not the view. A snapshot carries everything a *renderer* needs, which is more
than a reader wants — there is only one kind of object in the structure layer, a swing
point, and six fields point at one (`swing_price`, `leg_from_price`, `leg_to_price`,
`bos_level`, `extreme_high`, `extreme_low`). So the table shows the **facts** by default,
folds each event into one cell with the price it happened at (`swing` reads `high
27,642.50`), and hides the scaffolding a drawing needs: timestamps, leg endpoints, and
`trigger`, which is just `extreme ∓ RETRACE × range_scale`. **Details** brings all of it
back — 21 columns become 33. Nothing is ever dropped from the row itself.

The page **must be served** — opening `index.html` from the filesystem cannot work.
Starting reclaims the port from any older chart server, so they never stack;
`--stop` closes one and confirms the port is free.

## The vault and the catalog

Research on the session card runs on a hard discipline: **everything that costs zero
degrees of freedom happens before anything that costs one.** Description is free — looking
at explore distributions burns nothing. Decisions are not.

**The vault.** The most recent third of all London/NY sessions (from `SEALED_FROM =
2025-10-01`, `config/session_history.py`) is **sealed**: not plotted, not eyeballed, not
"just checked," until a rule is already frozen and gets its one honest evaluation. Split by
*time*, not at random — volatility clusters, so a randomly held-out Wednesday sits beside a
Tuesday that explored it and leaks straight through. The declaration lives in config; the
frozen receipt (`SESSION_SPLIT.json`, committed like `DATA_AUDIT.json`) records exactly
which sessions it seals — 817 explore, 395 sealed — and `src/session_history/split.py`
refuses to answer if the two ever disagree.

**The catalog** (`python -m src.cli.session_catalog`, `commands.bat` → Data) is the card
computed over every explore session, every bar — ~66k parquet rows through the *real*
indicators, never a reimplementation. It turns every N=1 anecdote into a population:
"does range expansion with rising efficiency separate real breaks from traps" stops being
an argument from three eyeballed sessions and becomes a query. The default build physically
cannot contain a sealed row. `src/session_history/README.md` maps the whole subsystem, the
order of operations, and the known debts (the N study predates the seal and was computed
over the full dataset — re-derive it explore-only before any sealed evaluation).

The percentile table is built per population, never in place: `NQT_5m_full.npz` and
`NQT_5m_explore.npz` are separate files, each stamped with what it was built from, and every
read names which one it wants. `FULL` is right for the live card, where the sealed third
genuinely is the past; `EXPLORE` is the only honest answer anywhere a rule is being
evaluated, since a full table ranks a bar against sessions that had not happened yet — and
that leaks as a *good backtest*, not an error.

**The strategy layer is being redefined and is currently absent**, so there is no
backtest or walk-forward door to run yet. The engines behind them (`backtest/`,
`optimize/`, `walkforward/`, `reporting/`) are intact and strategy-agnostic: a
strategy is anything with `entry_signals(bars)` emitting `Bracket` intents, and the
optimizer and walk-forward engine take a `build(params) -> strategy` callable, so
the door owns the catalogue and the engines stay generic.

When a backtest door returns it saves a **labeled run** to `runs/<timestamp>_<strategy>_<params>/` (git-ignored): `trades.csv`/`trades.txt`, `summary.json`/`summary.txt`, `equity.png`, and a `run.json` manifest that replays as a config.

_See `ARCHITECTURE.md` for all entry points. `src/broker/` is a reusable engine still awaiting its own command._

## Layout & docs

- `src/` — Python application code (live map: `ARCHITECTURE.md`)
- `frontend/` — browser code, self-contained, no build step (`frontend/README.md`)
- `data/` — market data, git-ignored (quality audit: `DATA_AUDIT.md`)
- `scratch/` — experiments & one-off tools, git-ignored
- `cache/` — packed bar cache, volume-at-price store, session catalog & history tables,
  server pidfile — git-ignored (rebuild: `--repack`, `python -m src.cli.vap`,
  `python -m src.cli.session_catalog`, `python -m src.cli.session_history`)
- `capture/` — recorded live market sessions (raw JSONL), git-ignored
- `projectX_API/` — ProjectX API reference docs
- `SESSION_SPLIT.json` — **frozen**: the vault receipt, which sessions are explore vs
  sealed (see `src/session_history/README.md`)
- `commands.bat` — the runnable command menu
- `BUILD_PLAN.md` — the phased build plan (what we decided, what we verified, what's next)
- `FIELDS.md` — **generated**: every snapshot field, its unit, its meaning, and the
  indicator, source file and config that produce it. `python -m src.cli.fields --write`
- `FIELDS_V2.md` — **generated**: the same contract as one table, one row per field
- `FIELDS_V3.md` — **hand-written**: the system map and the parameter-risk audit. The
  menu, the fields, and what they are wired to; then the census — 206 config constants,
  80 behavioural, **21 that shape a number a rule reads, and 0 fit to returns** — plus
  what a signal layer would cost in degrees of freedom, and what is already spent
- `CLAUDE.md` — project rules & conventions
- `requirements.txt` · `.env` (from `.env.example`) · `venv/` (git-ignored)
