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


## Indicators, in dependency order

| indicator | reads | source | config |
|---|---|---|---|
| **`sessions`** | the bar | `src/indicators/sessions.py` | `src/config/indicators/sessions.py` |
| **`orderflow`** | the bar | `src/indicators/orderflow.py` | `src/config/indicators/orderflow.py` |
| **`absorption`** | `orderflow` | `src/indicators/absorption.py` | `src/config/indicators/absorption.py` |
| **`range_scale`** | the bar | `src/indicators/range_scale.py` | `src/config/indicators/range_scale.py` |
| **`swing`** | `range_scale` | `src/indicators/swing.py` | `src/config/indicators/swing.py` |
| **`legs`** | `swing` | `src/indicators/legs.py` | `src/config/indicators/legs.py` |
| **`breaks`** | `swing` | `src/indicators/breaks.py` | `src/config/indicators/breaks.py` |
| **`profile`** | `range_scale`, `swing` | `src/indicators/profile.py` | `src/config/indicators/profile.py` |

## Fields

| field | published by | detail |
|---|---|---|
| `session` | `sessions` |  |
| `session_new` | `sessions` |  |
| `delta` | `orderflow` |  |
| `buy_volume` | `orderflow` |  |
| `sell_volume` | `orderflow` |  |
| `trades` | `orderflow` |  |
| `absorption` | `absorption` |  |
| `absorption_side` | `absorption` |  |
| `range_scale` | `range_scale` |  |
| `swing` | `swing` |  |
| `swing_price` | `swing` | yes |
| `swing_time` | `swing` | yes |
| `extreme_high` | `swing` |  |
| `extreme_high_time` | `swing` | yes |
| `extreme_low` | `swing` |  |
| `extreme_low_time` | `swing` | yes |
| `hunting` | `swing` |  |
| `retrace` | `swing` |  |
| `trigger` | `swing` | yes |
| `leg` | `legs` | yes |
| `leg_from_price` | `legs` | yes |
| `leg_from_time` | `legs` | yes |
| `leg_to_price` | `legs` | yes |
| `leg_to_time` | `legs` | yes |
| `bos` | `breaks` |  |
| `bos_level` | `breaks` | yes |
| `bos_time` | `breaks` | yes |
| `profile_poc` | `profile` |  |
| `profile_val` | `profile` | yes |
| `profile_vah` | `profile` | yes |
| `profile_from_time` | `profile` | yes |
| `profile_to_time` | `profile` | yes |
| `profile_volume` | `profile` |  |
| `profile_bins` | `profile` | yes |
| `profile_closed` | `profile` | yes |
| `value_width` | `profile` |  |
| `poc_position` | `profile` |  |
| `poc_distance` | `profile` |  |
| `price_vs_value` | `profile` |  |
| `delta_at_poc` | `profile` |  |

## What each indicator is for

- **`sessions`** — Publishes the current session, and whether this event opened it.
- **`orderflow`** — Publishes delta / buy_volume / sell_volume / trades, or nothing at all.
- **`absorption`** — Publishes whether the bar closed against its flow, and who absorbed.
- **`range_scale`** — Publishes the rolling median bar range, or nothing while it warms up.
- **`swing`** — Confirmed swing points, and the provisional extremes they come from.
- **`legs`** — Publishes the leg between the last two confirmed swing points.
- **`breaks`** — Publishes a break of structure on the bar that takes a swing level out.
- **`profile`** — The developing volume profile, and the finished ones behind it.
