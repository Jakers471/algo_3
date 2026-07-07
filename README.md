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
python -m src.cli.data NQ 5m                                    # load & summarize prepared bars
python -m src.cli.backtest run_configs/breakout_nq5m.json       # backtest -> saved labeled run
python -m src.cli.walkforward run_configs/wfa_breakout_nq5m.json  # walk-forward (IS/OOS) -> saved run
```

A backtest saves a **labeled run** to `runs/<timestamp>_<strategy>_<params>/` (git-ignored): `trades.csv`/`trades.txt`, `summary.json`/`summary.txt`, `equity.png`, and a `run.json` manifest that replays as a config. Run recipes live in `run_configs/` (tracked JSON) — see `run_configs/README.md` for every field and the swappable objective/strategy names.

_See `ARCHITECTURE.md` for all entry points. `src/broker/` is a reusable engine still awaiting its own command._

## Layout & docs

- `src/` — application code (live map: `ARCHITECTURE.md`)
- `data/` — market data, git-ignored (quality audit: `DATA_AUDIT.md`)
- `scratch/` — experiments & one-off tools, git-ignored
- `projectX_API/` — ProjectX API reference docs
- `commands.bat` — the runnable command menu
- `CLAUDE.md` — project rules & conventions
- `requirements.txt` · `.env` (from `.env.example`) · `venv/` (git-ignored)
