# FIELDS.md — the field contract

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


## Indicators, in dependency order

| indicator | reads | source | config |
|---|---|---|---|
| **`bar`** | the dataset | `src/chart/store.py` | `src/config/chart.py` |
| **`sessions`** | the bar | `src/indicators/sessions.py` | `src/config/indicators/sessions.py` |
| **`orderflow`** | the bar | `src/indicators/orderflow.py` | `src/config/indicators/orderflow.py` |
| **`absorption`** | `orderflow` | `src/indicators/absorption.py` | `src/config/indicators/absorption.py` |
| **`range_scale`** | the bar | `src/indicators/range_scale.py` | `src/config/indicators/range_scale.py` |
| **`swing`** | `range_scale` | `src/indicators/swing.py` | `src/config/indicators/swing.py` |
| **`legs`** | `swing` | `src/indicators/legs.py` | `src/config/indicators/legs.py` |
| **`breaks`** | `swing` | `src/indicators/breaks.py` | `src/config/indicators/breaks.py` |
| **`profile`** | `range_scale`, `swing` | `src/indicators/profile.py` | `src/config/indicators/profile.py` |

## Every field, defined

The blocks below are the table's blocks, in the order the columns appear.

The same contract as one flat table - every field in a single list, each
row naming its indicator - is in `FIELDS_V2.md`. Both are generated from
the same registry, so they cannot disagree.

### `bar`

The candle itself, straight from the packed dataset. No indicator computes it.

- **reads** — the dataset
- **source** — `src/chart/store.py`
- **config** — `src/config/chart.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `time` | epoch seconds, UTC | yes | The bar's CLOSE. A bar labelled T covers (T - step, T], so it is fully known at T and revealing it at T leaks nothing. |
| `open` | price | yes | First trade in the bar. |
| `high` | price | yes | Highest trade. |
| `low` | price | yes | Lowest trade. |
| `close` | price | yes | Last trade. Every structure rule that says 'closed through' means this one, not a wick. |
| `volume` | contracts | yes | Total traded. On tick-rebuilt bars it equals buy_volume + sell_volume, give or take the 0.000474% of prints that land between the quotes and join neither side. |

### `sessions`

Publishes the current session, and whether this event opened it.

- **reads** — the bar
- **source** — `src/indicators/sessions.py`
- **config** — `src/config/indicators/sessions.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `session` | Asia \| London \| NY \| None | yes | Which trading session this bar CLOSED in. None is the CME maintenance halt. Windows are Eastern, in config/session.py; membership is start < minute <= end because bars are close-stamped. |
| `session_new` | boolean | yes | True on the first bar of a session, including into and out of the halt. Derivable from `session` changing between rows - it is published because marks_for() sees one row and must decide whether to draw the rule. |

### `orderflow`

Publishes delta / buy_volume / sell_volume / trades, or nothing at all.

- **reads** — the bar
- **source** — `src/indicators/orderflow.py`
- **config** — `src/config/indicators/orderflow.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `delta` | contracts, signed | yes | buy_volume - sell_volume. Aggressive buying minus aggressive selling. NOT computed here: it was decided once, exactly, when bars were rebuilt from ticks - a print at the ask is a buyer, at the bid a seller. None on any bar file; never zero, which would claim the sides were balanced. |
| `buy_volume` | contracts | yes | Traded at the ask: someone crossed the spread to buy. |
| `sell_volume` | contracts | yes | Traded at the bid. buy + sell can fall short of volume: 0.000474% of CONTRACTS print strictly between the quotes and join neither side. How many BARS that touches depends on how long a bar is - 0.045% of 30s bars, 3.9% of 60m bars, up to 120 contracts on one - so the share of contracts is the invariant and the share of bars is not. |
| `trades` | count | yes | Number of prints in the bar. Not contracts - one print can carry many. |

### `absorption`

Publishes whether the bar closed against its flow, and who absorbed.

- **reads** — `orderflow`
- **source** — `src/indicators/absorption.py`
- **config** — `src/config/indicators/absorption.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `absorption` | boolean | yes | The bar closed AGAINST its own order flow: green on net selling, or red on net buying. Somebody resting absorbed the aggressors. Happens on 17.9% of bars; the candle explains only 56% of delta. Thresholds in config/indicators/absorption.py. |
| `absorption_side` | buy \| sell \| None | yes | Who absorbed. `buy` means price rose while sellers were the aggressors - a resting buyer. Marked BELOW the bar, because that is where the interest sat. |

### `range_scale`

Publishes the rolling median bar range, or nothing while it warms up.

- **reads** — the bar
- **source** — `src/indicators/range_scale.py`
- **config** — `src/config/indicators/range_scale.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `range_scale` | points | yes | The median bar range (high - low) over the last WINDOW_MINUTES of market time, floored at MIN_BARS bars. THE UNIT: every threshold and every ratio in the structure layer is measured in multiples of it. NQ's median 30s range moved 4.50 -> 14.25 across 29 months, so a number in points is right for one regime and silently wrong for the next. Absent on a dead tape - zero is no unit at all, not a small one. |

### `swing`

Confirmed swing points, and the provisional extremes they come from.

- **reads** — `range_scale`
- **source** — `src/indicators/swing.py`
- **config** — `src/config/indicators/swing.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `swing` | high \| low \| None | yes | A structure point CONFIRMED on this bar. Price retraced RETRACE x range_scale from the running extreme, proving it was a turn. Almost always None: it is an event, not a state. |
| `swing_price` | price |  | The price of that turn. |
| `swing_time` | epoch seconds, UTC |  | The EARLIER bar that made the extreme. A high does not announce itself; you learn it was one only after price falls away. That lag is the price of not looking ahead. |
| `extreme_high` | price | yes | The highest high since the last confirmed swing low. Live while `hunting` is high; frozen at the confirmed swing otherwise, which is why it can sit unchanged for many rows. |
| `extreme_high_time` | epoch seconds, UTC |  | The bar that made it. |
| `extreme_low` | price | yes | The lowest low since the last confirmed swing high. The mirror of extreme_high. |
| `extreme_low_time` | epoch seconds, UTC |  | The bar that made it. |
| `hunting` | high \| low | yes | Which rail is still PROVISIONAL - the one that could still move, and the kind the next confirmed swing will be. It does not predict direction: hunting a high while price falls is exactly what confirms that high. |
| `retrace` | x range_scale | yes | (live extreme - close) / range_scale, or the mirror. How far price has pulled back from the running extreme, in typical bars. Confirms at RETRACE. Dimensionless: 10x the prices and it does not move. Measured to the CLOSE while the trigger tests the LOW, so a swing can confirm on a bar reading slightly under RETRACE. |
| `trigger` | price |  | extreme -/+ RETRACE x range_scale. The price at which the provisional extreme becomes a swing. Rides up under a rising high, so it says what has to happen next. Pure arithmetic on columns already here; hidden from the table. |

### `legs`

Publishes the leg between the last two confirmed swing points.

- **reads** — `swing`
- **source** — `src/indicators/legs.py`
- **config** — `src/config/indicators/legs.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `leg` | up \| down \| None |  | The staircase segment that just closed, on the bar its far swing confirmed. Up if it ended above where it began. Swings alternate, so legs alternate: this is mechanical, not a market fact. |
| `leg_from_price` | price |  | The previous confirmed swing. A leg carries no information the swings do not - it is a drawing, and five columns of one. Hidden from the table. |
| `leg_from_time` | epoch seconds, UTC |  | The bar that MADE that swing. |
| `leg_to_price` | price |  | The swing that just confirmed. Identical to `swing_price` on the same row. |
| `leg_to_time` | epoch seconds, UTC |  | The bar that made it, earlier than this one. |

### `breaks`

Publishes a break of structure on the bar that takes a swing level out.

- **reads** — `swing`
- **source** — `src/indicators/breaks.py`
- **config** — `src/config/indicators/breaks.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `bos` | up \| down \| None | yes | Break of structure: this bar CLOSED through a standing swing level. Up means a swing high went. The level is then spent and fires once - one that re-broke every bar would be a drawing, not an event. A wick through that closes back is a rejection, not a break (USE_CLOSE). |
| `bos_level` | price |  | The price that broke: an older swing's price. |
| `bos_time` | epoch seconds, UTC |  | The bar that MADE the swing whose level broke, not the bar that broke it. |

### `profile`

The developing volume profile, and the finished ones behind it.

- **reads** — `range_scale`, `swing`
- **source** — `src/indicators/profile.py`
- **config** — `src/config/indicators/profile.py`

| field | unit | shown | what it is |
|---|---|---|---|
| `profile_poc` | price | yes | Point of control: the single bin where the most contracts changed hands. The market's own answer to what this is worth. The only absolute number in the block. |
| `profile_val` | price |  | Value area low. The bottom of the contiguous band around the POC holding 70% of the volume (config/profile.py VALUE_AREA). Drawn on the chart; `value_width` is what it says. |
| `profile_vah` | price |  | Value area high. The top of that same band. |
| `profile_from_time` | epoch seconds, UTC |  | Close time of the first bar in this range - the bar after the last confirmed swing. |
| `profile_to_time` | epoch seconds, UTC |  | Close time of the current bar. The range's right edge, which moves every bar. |
| `profile_volume` | contracts | yes | Total traded in the developing range. Climbs every bar, then resets when a swing confirms and a new range opens. Not comparable between two ranges. |
| `profile_bins` | payload |  | The histogram: [price, volume, buy_volume] per bin, bins `range_scale / BINS_PER_SCALE` wide. The chart draws it; the brain should never read it - a few hundred mostly-noise numbers where five readings will do. |
| `profile_closed` | payload |  | The last MAX_CLOSED finished profiles, each with the span it described. Frozen at the bar that MADE its swing. |
| `value_width` | x range_scale | yes | (VAH - VAL) / range_scale. How tightly the market agreed on a price. Narrow is balance; wide is a market that kept trading away from itself. NQ 15m: p05 1.62, median 4.25, p95 14.13. |
| `poc_position` | 0..1 | yes | (POC - lowest traded price) / (highest - lowest), over the prices traded IN THIS RANGE - not the bar's high and low. 0.5 is value in the middle; near 1 is value at the top with everything below merely traversed. NQ 15m median 0.61. |
| `poc_distance` | x range_scale | yes | (close - POC) / range_scale. How far price is from the fair price, in typical bars. Positive is above. NQ 15m: p05 -4.80, p95 +7.72. |
| `price_vs_value` | above \| inside \| below | yes | Where the close sits against the value area. Outside it, the market is declining to accept the price it just spent all that volume building. |
| `delta_at_poc` | -1..+1 | yes | (buy - sell) / volume, at the POC bin only. +1 means every contract at the fair price lifted the offer. Near zero by construction - the POC is where buyers and sellers AGREE - so the tail is the signal: \|x\| > 0.10 on 1.0% of bars, > 0.20 on none. Needs volume at price AND aggressor side; only ticks carry both. |
