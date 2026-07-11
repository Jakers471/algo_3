# scratch/ — experiments, one-off tools & analysis

A git-ignored working area, separate from the permanent `src/` codebase. Spikes, comparisons, audits, quick analyses, and tools you're not ready to commit live here.

- **git-ignored and outside the product — but NOT auto-deleted.** Code here persists and may have ongoing use (a comparison you re-run, an audit generator). Nothing here is removed unless Jake specifically says so.
- **Never** import `scratch/` from `src/`, and never write permanent product code here.
- When something here earns a permanent place, **promote** the reusable part into a proper `src/` module. Promotion is additive — it doesn't require deleting the scratch original.

See `CLAUDE.md` → "Scratch vs permanent" for the full rule.

## What's here

| File | Job | Runs? |
|------|-----|-------|
| `audit_parquet.py` | regenerate `DATA_AUDIT.json` / `.md` from the Parquet store | yes — wired into `commands.bat` → Data |
| `audit_project.py` | docs-drift + dead-code sweep | yes — `commands.bat` → Maintenance |
| `compare_data.py` | NT8 Parquet vs the ProjectX API bars | yes — `commands.bat` → Data |
| `analysis/break_sequences.py` | do breaks continue or alternate? measured against a base-rate and a shuffled null. **Its negative continuation edge is a swing-machine artifact — see `flow_edge.py`** | yes — `commands.bat` → Analysis |
| `analysis/seasonality_report.py` | why `range_scale`'s window is minutes, not bars — writes an HTML report | yes — `commands.bat` → Analysis |
| `analysis/timeframe_scaling.html` | `range ~ t^0.507`, and why 30s/3m/15m is evenly spaced | yes — open it |
| `analysis/leg_zoom.py` | one 15m leg, then every 3m leg inside it, then every 30s leg — three PNGs | yes — `commands.bat` → Analysis |
| `analysis/scale_ladder.py` | is `RETRACE` tunable? `swing` at eight thresholds at once; swing count vs threshold, log-log, against two nulls — two PNGs | yes — `commands.bat` → Analysis |
| `analysis/regime_plane.py` | is regime a thing? every leg as `(drift, impulse)`, both scale-free, against sign-flipped bars — three PNGs | yes — `commands.bat` → Analysis |
| `analysis/retracement.py` | `r = \|this leg\| / \|last leg\|` at three rungs: is `r < 1` more common than a random walk manages, and does it persist? — one PNG | yes — `commands.bat` → Analysis |
| `analysis/flow_edge.py` | does order flow at a break predict the next break? carries a placebo, a confound (`leg_bars`) and a sign-flipped null — one PNG | yes — `commands.bat` → Analysis |
| `analysis/outcomes.py` | **the target.** labels every bar with which barrier (`±k × range_scale`) price touched first — no swing machine on the outcome side. Prints the cost wall and the always-long benchmark a signal must beat; writes `outcomes_<sym>_<rung>.parquet` for the experiments after it — one PNG | yes — `commands.bat` → Analysis |
| `analysis/expectancy.py` | what does a bracket at a break of structure earn, after costs, against a sign-flipped null? picks the grid cell on one half and takes it on the other — one PNG | yes — `commands.bat` → Analysis |
| `analysis/profile_edge.py` | does the volume profile predict the size of the next leg once `range_scale` **and** the previous leg are divided out? — one PNG | yes — `commands.bat` → Analysis |
| `analysis/straddle.py` | buy the expansion, never the direction: a buy-stop at the VAH and a sell-stop at the VAL, risk one value width. Does a coil (`value_width / √age`) pick the ones worth taking, against the always-straddle benchmark? non-overlapping trades only — one PNG | yes — `commands.bat` → Analysis |
| `analysis/magnitude.py` | why the sign of a move is a coin and its size is not: `acf(r)` vs `acf(\|r\|)`, real against both nulls — three PNGs | yes — `commands.bat` → Analysis |
| `analysis/magnitude_paper.py` | the same result written up from first principles — raw bars, the arithmetic, then the summary. Self-contained HTML, figures embedded | yes — `commands.bat` → Analysis |
| `analysis/forecast_paper.py` | can you actually forecast tomorrow's volatility? HAR-RV, fitted on the first 60% of days and scored on the rest. The identical model on tomorrow's *return* is the control — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/edge_paper.py` | optional stopping, measured: on a martingale every bracket has expectancy zero, so reward:risk cannot beat a coin. What win rate you'd actually need, and your house edge vs roulette — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/discipline_paper.py` | is trading 90% risk management? Sizing multiplies an edge and cannot create one; 10,000 zero-skill traders; how many trades to tell skill from luck — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/hft_paper.py` | is tick data more predictable? The trade sign is (acf 0.46); the mid barely is (R2_oos 0.004) — and the predicted move is a fraction of the spread you must cross. Plus what is and is not legal in HFT — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/value_width_draw.py` | draws balanced (narrow) vs imbalanced (wide) value areas on real size-matched legs, with the honest size-controlled next-leg number — one PNG | yes — `commands.bat` → Analysis |
| `analysis/quant_report.py` | the alpha/beta tearsheet: regress each strategy on passive-long NQ, report alpha/t/beta/Sharpe/IR, information coefficients, and the multiple-testing correction — self-contained HTML, no candlesticks | yes — `commands.bat` → Analysis |
| `analysis/indicator_scan.py` | the systematic pass: run the whole indicator stack, engineer every publishable field into a dimensionless feature, and regress the lot against the next move's sign and size — out of sample, non-overlapping, with a placebo and the multiple-testing bar. Caches the walk — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/ma_scan.py` | are 10/20/50/100/200 MAs useful? Distance/slope/stack/ribbon as dimensionless features regressed vs next move (direction + magnitude), plus a golden/death-cross event study against the drift baseline — self-contained HTML | yes — `commands.bat` → Analysis |
| `analysis/ma_squeeze.py` | does the MA 'coiled spring' exist? Aligns every ribbon squeeze at t=0 and draws the forward expansion vs a baseline, the signed cone (direction), and real annotated examples. Finds squeeze -> LESS travel, not more — self-contained HTML | yes — `commands.bat` → Analysis |
| `mockups/structure_variants.py` | six ways to draw swings/legs/breaks on real bars — six PNGs | yes — `commands.bat` → Analysis |
| `mockups/pane/`, `mockups/native/` | throwaway pane mockups (browser + PySide6) for the snapshot table | yes — open / run directly |
| `va_breakout_demo.py` | decode a VA-breakout signal | **no** — imports the deleted `src/indicators/` and `src/strategy/` |
| `regime_census.py` | how common is each regime | **no** — imports the deleted `src.data.cache` |

The last two broke when the strategy layer was cleared (commit `0aec791`) ahead of its
redesign. They are kept, not deleted — scratch is never cleaned up without Jake saying so —
but their menu entries were removed because they cannot run. The code they called is
recoverable with `git show b671d12:src/indicators/grade.py` and friends.
