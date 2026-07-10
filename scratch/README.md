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
| `analysis/break_sequences.py` | do breaks continue or alternate? measured against a base-rate and a shuffled null | yes — `commands.bat` → Analysis |
| `analysis/seasonality_report.py` | why `range_scale`'s window is minutes, not bars — writes an HTML report | yes — `commands.bat` → Analysis |
| `analysis/timeframe_scaling.html` | `range ~ t^0.507`, and why 30s/3m/15m is evenly spaced | yes — open it |
| `analysis/leg_zoom.py` | one 15m leg, then every 3m leg inside it, then every 30s leg — three PNGs | yes — `commands.bat` → Analysis |
| `mockups/structure_variants.py` | six ways to draw swings/legs/breaks on real bars — six PNGs | yes — `commands.bat` → Analysis |
| `mockups/pane/`, `mockups/native/` | throwaway pane mockups (browser + PySide6) for the snapshot table | yes — open / run directly |
| `va_breakout_demo.py` | decode a VA-breakout signal | **no** — imports the deleted `src/indicators/` and `src/strategy/` |
| `regime_census.py` | how common is each regime | **no** — imports the deleted `src.data.cache` |

The last two broke when the strategy layer was cleared (commit `0aec791`) ahead of its
redesign. They are kept, not deleted — scratch is never cleaned up without Jake saying so —
but their menu entries were removed because they cannot run. The code they called is
recoverable with `git show b671d12:src/indicators/grade.py` and friends.
