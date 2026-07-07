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

Or run a door directly, e.g. load and summarize prepared bars:

```
python -m src.cli.data NQ 5m
```

_See `ARCHITECTURE.md` for all entry points. `src/broker/` is a reusable engine still awaiting its own command._

## Layout & docs

- `src/` — application code (live map: `ARCHITECTURE.md`)
- `data/` — market data, git-ignored (quality audit: `DATA_AUDIT.md`)
- `scratch/` — experiments & one-off tools, git-ignored
- `projectX_API/` — ProjectX API reference docs
- `commands.bat` — the runnable command menu
- `CLAUDE.md` — project rules & conventions
- `requirements.txt` · `.env` (from `.env.example`) · `venv/` (git-ignored)
