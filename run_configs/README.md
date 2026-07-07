# run_configs/ — backtest & walk-forward run recipes

JSON files that define a run. Each doubles as the format of the saved manifest
(`run.json` / `wfa.json`), so any past run in `runs/` is replayable by pointing
a CLI at its manifest. JSON has no comments — the valid values live here.

## One file = one recipe (the filename must match its strategy)

A config is a **saved recipe named for its contents**, not a file you edit into a
different strategy. The CLI dispatches on the `strategy` field *inside* the JSON
(via the registry) — the filename is a human label. To keep names honest, loading
a config **fails** if the filename doesn't contain the `strategy` name. So:

- Point the CLI at **any** config file — it runs whatever's inside. That's the
  plug-and-play: many recipes, one CLI.
- Want a different strategy/symbol/params? **Make a new file** named for it
  (e.g. `va_breakout_nq1m.json`). Don't repurpose `breakout_nq5m.json`.
- Saved run manifests (`run.json` / `wfa.json`) are exempt — they always replay.

## Backtest run config (e.g. `breakout_nq5m.json`)

Run with: `python -m src.cli.backtest run_configs/breakout_nq5m.json`

| Field | Type | Meaning |
|-------|------|---------|
| `strategy` | string | which strategy — see **Strategies** below |
| `params` | object | that strategy's parameters — see **Strategies** |
| `symbol` | string | `NQ` or `ES` |
| `timeframe` | string | `1m`, `5m`, `15m`, `60m`, `1d` (`ES` has no `1d`) |
| `size` | int | contracts per trade (fixed for now; the risk engine will size later) |

## Walk-forward config (e.g. `wfa_breakout_nq5m.json`)

Run with: `python -m src.cli.walkforward run_configs/wfa_breakout_nq5m.json`

Same `strategy` / `symbol` / `timeframe` / `size` as above, plus:

| Field | Type | Meaning |
|-------|------|---------|
| `objective` | string | what to optimize in-sample — see **Objectives** below |
| `param_grid` | object | each strategy param → a list of values to search (all combos are tried) |
| `is_days` | int | in-sample (optimize) window length, in days |
| `oos_days` | int | out-of-sample (test) window length, in days |
| `step_days` | int | how far each fold slides forward (usually = `oos_days`) |
| `anchored` | bool | `false` = rolling IS window; `true` = fixed IS start that grows |
| `min_trades` | int | reject in-sample combos with fewer trades (selection-bias guard) |

Judge a walk-forward on the **stitched out-of-sample** result, never the
in-sample optimization.

## Objectives (swap the `objective` string for any of these)

Higher is always better; the optimizer maximizes it.

- `profit_factor` — gross profit ÷ gross loss
- `net_profit` — total $ PnL
- `sharpe` — per-trade mean ÷ std (not annualized)
- `sortino` — per-trade mean ÷ downside std
- `expectancy` — average $ per trade
- `win_rate` — fraction of winning trades

## Strategies (swap the `strategy` string; set `params` / `param_grid` to match)

- `breakout` — Donchian breakout, long or short. Params:
  - `lookback` (int) — bars for the rolling high/low stop-entry
  - `stop_points` (float) — stop-loss distance in points
  - `target_points` (float) — take-profit distance in points
  - `direction` (string) — `"long"` (buy-stop at the rolling high) or `"short"`
    (sell-stop at the rolling low); default `"long"`. One direction at a time.
    In a walk-forward `param_grid` you can sweep `"direction": ["long", "short"]`
    to let the optimizer pick per fold.

_Registered strategies live in `src/strategy/registry.py`; add a strategy there
and it becomes usable by name here._
