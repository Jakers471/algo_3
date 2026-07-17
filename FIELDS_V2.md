# FIELDS_V2.md — the field contract, as one table

**Generated. Do not edit by hand.** Run `python -m src.cli.fields --write` (or
`commands.bat` -> Maintenance) and commit the result alongside the code that
changed it.

Every column in the snapshot table, and every value the brain will read, is
published by exactly one indicator. This says which — and where its code and its
dials live, so a name in a row is always one click from the file that produced it.

Indicators run in **dependency order**: an indicator's fields exist before any
indicator that reads them runs. `depends` is that edge; the registry topologically
sorts on it, and a cycle is a startup error rather than a wrong number three hours
into a backtest.

A field marked **detail** is scaffolding a drawing needs and a reader does not — a
timestamp, an endpoint, or arithmetic on a column already shown. The table hides
those unless you click **Details**. Nothing is ever dropped from the row itself.

One row per field, in the order the table's columns appear, each carrying the
indicator that owns it. The indicator is named once, on the first field of its
block, the same way the table's header names it once — so the blocks stay legible
and the column that says *where this came from* does not become wallpaper.

`FIELDS.md` is the same contract with a section per indicator, and the source and
config files each one lives in.

## Read the unit first

It is the thing that goes wrong first, because three of them look identical in a
table and mean completely different things.

| unit | what it does when the market changes |
|---|---|
| `price` | moves with the market. 30,698.50 means nothing next month |
| `points` | moves with volatility. Ten points is a lot at 04:00 and nothing at the open |
| `x range_scale` | moves with neither. **Dimensionless.** Multiply every price by ten and it does not change |
| `contracts` | a count. Comparable within a range, not between two of them |
| `0..1`, `-1..+1` | a ratio, already normalised |
| `epoch seconds, UTC` | a timestamp. Ten digits, not a price |
| `payload` | a structure the chart draws. Never read it as a number |

`range_scale` itself is in **points** — it is the ruler, and the only thing in the
structure layer that has to be. Everything measured *in* it is dimensionless, which
is the entire reason the rules survive a change of regime.


## Where each indicator lives

| indicator | reads | source | config |
|---|---|---|---|
| **`bar`** | the dataset | `src/chart/store.py` | `src/config/chart.py` |
| **`sessions`** | the bar | `src/indicators/sessions.py` | `src/config/indicators/sessions.py` |
| **`range_scale`** | the bar | `src/indicators/range_scale.py` | `src/config/indicators/range_scale.py` |
| **`session_stats`** | `sessions`, `range_scale` | `src/indicators/session_stats.py` | `src/config/indicators/session_stats.py` |
| **`orderflow`** | the bar | `src/indicators/orderflow.py` | `src/config/indicators/orderflow.py` |
| **`absorption`** | `orderflow` | `src/indicators/absorption.py` | `src/config/indicators/absorption.py` |
| **`swing`** | `range_scale` | `src/indicators/swing.py` | `src/config/indicators/swing.py` |
| **`legs`** | `swing` | `src/indicators/legs.py` | `src/config/indicators/legs.py` |
| **`breaks`** | `swing` | `src/indicators/breaks.py` | `src/config/indicators/breaks.py` |
| **`ribbon`** | the bar | `src/indicators/ribbon.py` | `src/config/indicators/ribbon.py` |
| **`regime`** | `ribbon`, `range_scale` | `src/indicators/regime.py` | `src/config/indicators/regime.py` |
| **`ma`** | the bar | `src/indicators/ma.py` | `src/config/indicators/ma.py` |
| **`profile`** | `range_scale`, `swing` | `src/indicators/profile.py` | `src/config/indicators/profile.py` |

## Every field, defined

Every column of the snapshot table, in the order the columns appear,
under the indicator that publishes it. `shown` is what the table does
with it: **yes** by default, **detail** only when you click Details.

| indicator | field | unit | shown | what it is |
|---|---|---|---|---|
| **`bar`** | `time` | epoch seconds, UTC | yes | The bar's CLOSE. A bar labelled T covers (T - step, T], so it is fully known at T and revealing it at T leaks nothing. |
|  | `open` | price | yes | First trade in the bar. |
|  | `high` | price | yes | Highest trade. |
|  | `low` | price | yes | Lowest trade. |
|  | `close` | price | yes | Last trade. Every structure rule that says 'closed through' means this one, not a wick. |
|  | `volume` | contracts | yes | Total traded. On tick-rebuilt bars it equals buy_volume + sell_volume, give or take the 0.000474% of prints that land between the quotes and join neither side. |
| **`sessions`** | `session` | Asia \| London \| NY \| None | yes | Which trading session this bar CLOSED in. None is the CME maintenance halt. Windows are Eastern, in config/session.py; membership is start < minute <= end because bars are close-stamped. |
|  | `session_new` | boolean | yes | True on the first bar of a session, including into and out of the halt. Derivable from `session` changing between rows - it is published because marks_for() sees one row and must decide whether to draw the rule. |
| **`range_scale`** | `range_scale` | points | yes | The median bar range (high - low) over the last WINDOW_MINUTES of market time, floored at MIN_BARS bars. THE UNIT: every threshold and every ratio in the structure layer is measured in multiples of it. NQ's median 30s range moved 4.50 -> 14.25 across 29 months, so a number in points is right for one regime and silently wrong for the next. Absent on a dead tape - zero is no unit at all, not a small one. |
| **`session_stats`** | `session_range` | x range_scale | yes | (session_high - session_low) / range_scale, so far. None until range_scale itself has warmed up. |
|  | `session_bars` | count | yes | Bars seen since the session opened. |
|  | `session_net` | x range_scale | yes | (close - session_open) / range_scale. Signed: negative is a session that sold off. |
|  | `session_net_ratio` | -1..+1 | yes | session_net / session_range. How much of the session's own range the net move actually covered - direction and strength in one number. |
|  | `session_closed_ratio` | 0..1 | yes | (close - session_low) / session_range. Where price sits right now inside the session's own range. Near 0 is at the low, near 1 at the high. |
|  | `session_body_ratio` | 0..1 | yes | \|session_net\| / range, treating the whole session as one candle. body + up-wick + low-wick sum to 1. |
|  | `session_upwick_ratio` | 0..1 | yes | (session_high - max(open, close)) / range. |
|  | `session_lowwick_ratio` | 0..1 | yes | (min(open, close) - session_low) / range. |
|  | `session_travel` | x range_scale | yes | Sum of every bar's own (high - low) since the open, / range_scale - how far price actually walked, not just where it ended up. |
|  | `session_efficiency` | 0..1 | yes | session_range / session_travel. 1.0 is a straight line from open to now; a small number is a session that covered a lot of ground for little net progress - the ratio companion to session_dir_changes. |
|  | `session_dir_changes` | count | yes | Times the close-to-close direction flipped sign since the open. A counting measure: how choppy the session read, with no points threshold to calibrate. |
|  | `session_high_at_ratio` | 0..1 | yes | How far into the session (by bar count) the running high was set. Near 0 is early - the high was made and defended. |
|  | `session_low_at_ratio` | 0..1 | yes | The same, for the running low. |
|  | `session_volume` | contracts | yes | Total volume since the session opened. None on a bar file - use a tick-rebuilt dataset (NQT). |
|  | `session_delta` | contracts, signed | yes | Sum of buy_volume - sell_volume since the session opened. None on a bar file, never a proxy zero. |
|  | `session_poc` | price | yes | The session's own point of control: the single price with the most volume traded at it since the open. None without volume at price (NQT + python -m src.cli.vap); None until range_scale has warmed up - the bins it sizes; and None while the chart's Profile toggle is off, the same switch `profile` itself uses - volume at price is a per-bar store lookup, and the switch exists so a plain browse never pays for it unasked. |
|  | `session_poc_ratio` | 0..1 | yes | (session_poc - session_low) / session_range. Where the market's fair price sits inside the range it built to find it. |
|  | `session_val` | price | detail | Value area low: the bottom of the contiguous band around the POC holding config.profile.VALUE_AREA of the session's volume so far. |
|  | `session_vah` | price | detail | Value area high: the top of that same band. |
|  | `session_bins` | payload | detail | The session's own histogram so far: [price, volume, buy_volume] per bin, bins range_scale / BINS_PER_SCALE wide. The chart draws it; nothing else should read it - five readings already say what it says. |
|  | `session_from_time` | epoch seconds, UTC | detail | Close time of the session's first bar - where the profile drawing anchors. |
|  | `session_to_time` | epoch seconds, UTC | detail | Close time of the current bar - the profile's right edge, moving every bar. |
| **`orderflow`** | `delta` | contracts, signed | yes | buy_volume - sell_volume. Aggressive buying minus aggressive selling. NOT computed here: it was decided once, exactly, when bars were rebuilt from ticks - a print at the ask is a buyer, at the bid a seller. None on any bar file; never zero, which would claim the sides were balanced. |
|  | `buy_volume` | contracts | yes | Traded at the ask: someone crossed the spread to buy. |
|  | `sell_volume` | contracts | yes | Traded at the bid. buy + sell can fall short of volume: 0.000474% of CONTRACTS print strictly between the quotes and join neither side. How many BARS that touches depends on how long a bar is - 0.045% of 30s bars, 3.9% of 60m bars, up to 120 contracts on one - so the share of contracts is the invariant and the share of bars is not. |
|  | `trades` | count | yes | Number of prints in the bar. Not contracts - one print can carry many. |
| **`absorption`** | `absorption` | boolean | yes | The bar closed AGAINST its own order flow: green on net selling, or red on net buying. Somebody resting absorbed the aggressors. Happens on 17.9% of bars; the candle explains only 56% of delta. Thresholds in config/indicators/absorption.py. |
|  | `absorption_side` | buy \| sell \| None | yes | Who absorbed. `buy` means price rose while sellers were the aggressors - a resting buyer. Marked BELOW the bar, because that is where the interest sat. |
| **`swing`** | `swing` | high \| low \| None | yes | A structure point CONFIRMED on this bar. Price retraced RETRACE x range_scale from the running extreme, proving it was a turn. Almost always None: it is an event, not a state. |
|  | `swing_price` | price | detail | The price of that turn. |
|  | `swing_time` | epoch seconds, UTC | detail | The EARLIER bar that made the extreme. A high does not announce itself; you learn it was one only after price falls away. That lag is the price of not looking ahead. |
|  | `extreme_high` | price | yes | The highest high since the last confirmed swing low. Live while `hunting` is high; frozen at the confirmed swing otherwise, which is why it can sit unchanged for many rows. |
|  | `extreme_high_time` | epoch seconds, UTC | detail | The bar that made it. |
|  | `extreme_low` | price | yes | The lowest low since the last confirmed swing high. The mirror of extreme_high. |
|  | `extreme_low_time` | epoch seconds, UTC | detail | The bar that made it. |
|  | `hunting` | high \| low | yes | Which rail is still PROVISIONAL - the one that could still move, and the kind the next confirmed swing will be. It does not predict direction: hunting a high while price falls is exactly what confirms that high. |
|  | `retrace` | x range_scale | yes | (live extreme - close) / range_scale, or the mirror. How far price has pulled back from the running extreme, in typical bars. Confirms at RETRACE. Dimensionless: 10x the prices and it does not move. Measured to the CLOSE while the trigger tests the LOW, so a swing can confirm on a bar reading slightly under RETRACE. |
|  | `trigger` | price | detail | extreme -/+ RETRACE x range_scale. The price at which the provisional extreme becomes a swing. Rides up under a rising high, so it says what has to happen next. Pure arithmetic on columns already here; hidden from the table. |
| **`legs`** | `leg` | up \| down \| None | detail | The staircase segment that just closed, on the bar its far swing confirmed. Up if it ended above where it began. Swings alternate, so legs alternate: this is mechanical, not a market fact. |
|  | `leg_from_price` | price | detail | The previous confirmed swing. A leg carries no information the swings do not - it is a drawing, and five columns of one. Hidden from the table. |
|  | `leg_from_time` | epoch seconds, UTC | detail | The bar that MADE that swing. |
|  | `leg_to_price` | price | detail | The swing that just confirmed. Identical to `swing_price` on the same row. |
|  | `leg_to_time` | epoch seconds, UTC | detail | The bar that made it, earlier than this one. |
| **`breaks`** | `bos` | up \| down \| None | yes | Break of structure: this bar CLOSED through a standing swing level. Up means a swing high went. The level is then spent and fires once - one that re-broke every bar would be a drawing, not an event. A wick through that closes back is a rejection, not a break (USE_CLOSE). |
|  | `bos_level` | price | detail | The price that broke: an older swing's price. |
|  | `bos_time` | epoch seconds, UTC | detail | The bar that MADE the swing whose level broke, not the bar that broke it. |
| **`ribbon`** | `ribbon` | price | detail | One value per moving-average line, in the order of config PERIODS (short to long). Each is the simple mean of the last `period` closes, or None while that line still has fewer than `period` closes to average. A drawing, not a reading: the fan is on the chart, not in the table. |
|  | `ribbon_prev` | price | detail | The same lines' values on the PREVIOUS bar, carried forward so the chart can colour each segment by its slope - green where the line rose, red where it fell. Detail: it is half of a line the chart draws. |
| **`regime`** | `ribbon_align` | -1..+1 | yes | How well the ribbon is stacked in period order, over its 31 adjacent pairs. +1 short-over-long throughout (a clean up-trend), -1 fully inverted (a clean down-trend), 0 a scrambled fan. The sortedness of the fan: zero inversions is a trend. |
|  | `ribbon_agree` | -1..+1 | yes | The share of ribbon lines rising this bar minus the share falling. +1 all rising, -1 all falling. It leads alignment - a line's slope turns before its position in the stack does. |
|  | `ribbon_width` | x range_scale | yes | The fan's flare: (highest line - lowest line) over range_scale. By the (N-1)/2 lag geometry it is proportional to price velocity - wide is a trend with conviction, near zero is a squeeze. In range_scale so a cutoff survives a change of regime. |
|  | `regime` | up \| down \| chop \| transition \| None | yes | The market's state read off the fan: a trend (up/down) when the lines are stacked and flared, a transition when the fan has pinched shut, chop otherwise. Absent until the fan is fully warm. |
|  | `regime_new` | boolean | detail | True on the bar the regime CHANGED - what the chart draws a rule on. Detail: scaffolding for the drawing, not a reading. |
| **`ma`** | `ma` | price | yes | One value per line in config ACTIVE (the ENABLED entries of LINES, in order). Each is the simple mean of the last `period` closes, or None while that line still has fewer than `period` closes to average. A drawing, not a reading: the lines are on the chart, not in the table. |
|  | `ma_prev` | price | yes | The same lines' values on the PREVIOUS bar, carried forward so the chart can draw a segment from the last bar to this one without keeping its own state. |
| **`profile`** | `profile_poc` | price | yes | Point of control: the single bin where the most contracts changed hands. The market's own answer to what this is worth. The only absolute number in the block. |
|  | `profile_val` | price | detail | Value area low. The bottom of the contiguous band around the POC holding 70% of the volume (config/profile.py VALUE_AREA). Drawn on the chart; `value_width` is what it says. |
|  | `profile_vah` | price | detail | Value area high. The top of that same band. |
|  | `profile_from_time` | epoch seconds, UTC | detail | Close time of the first bar in this range - the bar after the last confirmed swing. |
|  | `profile_to_time` | epoch seconds, UTC | detail | Close time of the current bar. The range's right edge, which moves every bar. |
|  | `profile_volume` | contracts | yes | Total traded in the developing range. Climbs every bar, then resets when a swing confirms and a new range opens. Not comparable between two ranges. |
|  | `profile_bins` | payload | detail | The histogram: [price, volume, buy_volume] per bin, bins `range_scale / BINS_PER_SCALE` wide. The chart draws it; the brain should never read it - a few hundred mostly-noise numbers where five readings will do. |
|  | `profile_closed` | payload | detail | The last MAX_CLOSED finished profiles, each with the span it described. Frozen at the bar that MADE its swing. |
|  | `value_width` | x range_scale | yes | (VAH - VAL) / range_scale. How tightly the market agreed on a price. Narrow is balance; wide is a market that kept trading away from itself. NQ 15m: p05 1.62, median 4.25, p95 14.13. |
|  | `poc_position` | 0..1 | yes | (POC - lowest traded price) / (highest - lowest), over the prices traded IN THIS RANGE - not the bar's high and low. 0.5 is value in the middle; near 1 is value at the top with everything below merely traversed. NQ 15m median 0.61. |
|  | `poc_distance` | x range_scale | yes | (close - POC) / range_scale. How far price is from the fair price, in typical bars. Positive is above. NQ 15m: p05 -4.80, p95 +7.72. |
|  | `price_vs_value` | above \| inside \| below | yes | Where the close sits against the value area. Outside it, the market is declining to accept the price it just spent all that volume building. |
|  | `delta_at_poc` | -1..+1 | yes | (buy - sell) / volume, at the POC bin only. +1 means every contract at the fair price lifted the offer. Near zero by construction - the POC is where buyers and sellers AGREE - so the tail is the signal: \|x\| > 0.10 on 1.0% of bars, > 0.20 on none. Needs volume at price AND aggressor side; only ticks carry both. |

## What each indicator is for

**`sessions`** — reads the bar. Publishes the current session, and whether this event opened it.

**`range_scale`** — reads the bar. Publishes the rolling median bar range, or nothing while it warms up.

**`session_stats`** — reads `sessions`, `range_scale`. Publishes the running session scorecard, or nothing outside London/NY.

**`orderflow`** — reads the bar. Publishes delta / buy_volume / sell_volume / trades, or nothing at all.

**`absorption`** — reads `orderflow`. Publishes whether the bar closed against its flow, and who absorbed.

**`swing`** — reads `range_scale`. Confirmed swing points, and the provisional extremes they come from.

**`legs`** — reads `swing`. Publishes the leg between the last two confirmed swing points.

**`breaks`** — reads `swing`. Publishes a break of structure on the bar that takes a swing level out.

**`ribbon`** — reads the bar. Publishes the value of each moving-average line, and its previous value.

**`regime`** — reads `ribbon`, `range_scale`. Publishes the ribbon's alignment, agreement, width, and a regime label.

**`ma`** — reads the bar. Publishes the value of each enabled named moving average, and its previous value.

**`profile`** — reads `range_scale`, `swing`. The developing volume profile, and the finished ones behind it.

