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
1x/2x/4x, `Space` and `→`). Zoom and pan stay free the whole time.

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

**Structure** is drawn in two layers. A muted green or red **staircase** connects each
confirmed swing to the next — square corners, because a diagonal would claim price
travelled in a straight line between them, and the candles in between already say
otherwise. Over it, a **break of structure**: when a bar *closes* through a standing swing
level, a bright line runs from the swing that set the level, along it, to the close that
took it out. Green when a swing high goes, red when a swing low does. A level fires once
and is spent.

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

`delta_at_poc` is the one almost nothing else can compute: it needs volume at price **and**
aggressor side, and both live only in the ticks. It sits near zero by construction — the
point of control is where buyers and sellers *agree* — so the tail is the signal, not the
centre. `|delta_at_poc| > 0.10` on 1.0% of bars.

Volume at price lives only in the ticks: a bar records its total volume, its high and its
low, never where between them the contracts changed hands. So it is folded once into a
packed store (`python -m src.cli.vap`, ~80s, git-ignored), and the control is **disabled on
symbols that have no ticks** rather than offered and quietly drawing nothing.

The chart draws; it does not compute. Indicators are computed once in Python and arrive
over `/api/overlays` as drawing instructions — a dashed, labelled rule at each
trading-session open (Asia / London / NY), and arrows at the swings. Both are shapes the
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

Columns are not configured anywhere: the first six describe the bar, the rest are whatever
fields the session publishes, **grouped under the indicator that published them**. Add an
indicator and a block appears.

**Every column says where it came from.** Each block is tinted with its indicator's own
hue, a hairline marks the seam between blocks, and a legend along the bottom names them.
The colour rides the *header*, never a cell — a cell's colour already means green-up,
red-down, grey-absent, and two meanings on one pixel is one meaning too many.

**Hover any column header** and it tells you which indicator owns it, what unit the number
is in, and what it means. `price`, `points` and `x range_scale` look identical in a table
and behave completely differently when the market changes — the unit comes first.

The same text, for every field, is **`FIELDS.md`** — generated by `python -m src.cli.fields
--write` from definitions that live beside the code that computes each number. A test fails
if a field has no definition, if its unit is unrecognised, or if the file goes stale.

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
- `cache/` — packed bar cache, volume-at-price store & server pidfile, git-ignored
  (rebuild: `--repack`, and `python -m src.cli.vap`)
- `capture/` — recorded live market sessions (raw JSONL), git-ignored
- `projectX_API/` — ProjectX API reference docs
- `commands.bat` — the runnable command menu
- `BUILD_PLAN.md` — the phased build plan (what we decided, what we verified, what's next)
- `FIELDS.md` — **generated**: every snapshot field, its unit, its meaning, and the
  indicator, source file and config that produce it. `python -m src.cli.fields --write`
- `CLAUDE.md` — project rules & conventions
- `requirements.txt` · `.env` (from `.env.example`) · `venv/` (git-ignored)
