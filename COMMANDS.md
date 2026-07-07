# Commands

Every runnable command in this project. Run all of them from the repo root
(`C:\Users\jakers\Desktop\algo_3`). **Whenever a command is added or changed,
update this file in the same commit.**

## Setup (one time)

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Secrets live in a git-ignored `.env` at the repo root (already set up):

```
PROJECTX_USERNAME=...
PROJECTX_API_KEY=...
PROJECTX_TOKEN=...
```

## CLI

| Command | What it does |
|---------|--------------|
| `python -m src.cli.connect` | Connect to ProjectX, list + select a tradable account, resolve the front-month E-mini NQ contract, and fetch recent hourly bars. Prints a color-coded summary. |

### `python -m src.cli.connect`

Connects using the token in `.env` (auto-validates; falls back to an API-key
login if the token is expired), then walks three steps:

1. **Connect** to the ProjectX Gateway API.
2. **Select an account** — lists all active accounts and picks the first tradable one.
3. **Grab NQ data** — resolves the E-mini NQ contract and pulls the last 7 days of hourly bars.

Output is written to the console (colored) and appended to `logs/algo.log` (plain).
