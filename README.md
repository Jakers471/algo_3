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

The chart draws; it does not compute. Indicators are computed once in Python and arrive
over `/api/overlays` as drawing instructions — today a dashed, labelled rule at each
trading-session open (Asia / London / NY), straight from `src/indicators/sessions.py`.
Because the overlay request carries only the bars replay has revealed, a drawing can never
leak the future. See `BUILD_PLAN.md` for the road from here.

Editing HTML/CSS/JS? Just refresh the page. Editing Python? Add `--reload` and the server
restarts itself.

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
- `cache/` — packed bar cache & server pidfile, git-ignored (rebuild: `--repack`)
- `capture/` — recorded live market sessions (raw JSONL), git-ignored
- `projectX_API/` — ProjectX API reference docs
- `commands.bat` — the runnable command menu
- `BUILD_PLAN.md` — the phased build plan (what we decided, what we verified, what's next)
- `CLAUDE.md` — project rules & conventions
- `requirements.txt` · `.env` (from `.env.example`) · `venv/` (git-ignored)
