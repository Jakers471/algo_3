# Commands

Run from repo root. Update this file whenever a command changes.

## Setup

| Command | Source |
|---------|--------|
| `python -m pip install -r requirements.txt` | `requirements.txt` |

## CLI

| Command | Source | Does |
|---------|--------|------|
| `python -m src.cli.fetch` | `src/cli/fetch.py` | Fetch all available NQ history (every timeframe) → save `data/NQ_<TF>.csv` |

_For detail, read the source file — its imports and functions are the spec._
