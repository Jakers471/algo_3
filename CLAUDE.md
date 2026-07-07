# CLAUDE.md

## Project structure

**All code lives under `src/`. Keep `src/` clean.**

- The top level is for config, docs, dependency lists, and git files only — things like `CLAUDE.md`, `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env`. Keep these out of the way and out of `src/`.
- Every source file you write, create, or move goes under `src/` (in an appropriate subpackage). Do not put code at the top level.
- Reference/data directories (e.g. `projectX_API/`, `data/`) are not code and stay at the top level, not in `src/`.

### Folders by category — never loose files

**Every file lives in a labeled subpackage named for its category. No loose files ever** — `src/` itself holds only `__init__.py` and subpackage folders, never a stray `.py`.

- Group by what a file *is about*, and let the folder name say it: `config/` (settings), `core/` (shared infra like console + logging setup), `broker/` (API access), `cli/` (interface), and so on. The folder is the label; the label is the category.
- The moment a second file of the same category appears, they share a folder. A category never lives loose next to unrelated files.
- If a new file doesn't fit any existing category, create a new labeled folder for it — do not drop it at `src/` root "for now". There is no "for now"; loose files never happen.
- Current layout: `src/config/`, `src/core/`, `src/broker/`, `src/cli/`. New areas (`strategy/`, `backtest/`, `risk/`, `data/` loaders, etc.) get their own folder as they arrive.

### One file = one job

**Each file does one job — it has one reason to exist and one reason to change.** This keeps the codebase clean, organised, and easy to understand, build on, and debug.

- Before writing a line, name what it *does* ("this logs in", "this fetches bars", "this calculates Sharpe"). The verb tells you the file. If a line doesn't fit any existing file's job, that's a new file.
- Split by **who needs what**. If two callers need different parts of a file, those parts belong in separate files so each caller imports only the half it needs (e.g. `broker/client.py` for the shared connection, `broker/history.py` for bars, `broker/orders.py` for order actions).
- Separate **plumbing from logic**. Code that talks to the outside world (API calls, file read/write) stays apart from your actual decision logic (strategy, backtest math), so logic can be tested without touching the API.
- **Keep interface files thin.** A CLI command or `main.py` just parses input, calls the real function in a module, and formats the result — it holds no trading logic itself. The weight lives in the modules; the doors on top stay feather-light.
- **Split when it hurts, not before.** It's fine to start with one file and break it apart the moment a second caller needs only part of it. Don't over-plan the structure up front — let the seams reveal themselves and refactor toward one-job-per-file as they do.
- **A compound request is not a request for one script.** When Jake bundles several actions in one breath — "connect to ProjectX, grab accounts, fetch NQ data", or "x, y and z", or "this, this and that" — that is a list of *separate jobs*, each getting its own file, even though he didn't say "split it up." This is a trading algorithm built from many small, modular pieces; default to modularity. When in doubt, split.
- **Never duplicate logic.** If something already exists, reuse it — import the existing file, don't rewrite it. When Jake reiterates "I need you to build X" and we already have X (or a piece of it), do NOT re-create it; extend or call what's there. Every file is reusable and pluggable: written once, imported everywhere. Duplicated logic is a bug.

### Logging & debug

**Use Python's `logging` module, never bare `print`, for all debug/progress output.** `logging` has levels you can dial up or down without deleting code; `print` is permanent noise.

- **Log calls go inline** in the `.py` file doing the work — a `logger.info("completed X")` narrates the job it sits next to. This does not violate one-file-one-job; a log line reports on the file's existing job.
- Use levels deliberately: `logger.debug()` for noisy detail (bug hunting), `logger.info()` for normal "completed / doing" progress, `logger.warning()` / `logger.error()` for problems. Set level to `DEBUG` while debugging, `INFO` when running normally — no lines get deleted.
- **Log *configuration* is its own job** — format, level, and destinations live in one module (e.g. `src/logging_config.py`) with a `setup_logging()` called once at startup by the CLI/`main.py`. Change format or add a log file in that one place; every module follows.
- Each module gets its logger with `logger = logging.getLogger(__name__)` at the top. Modules decide *what* to log; `logging_config.py` decides *how and where*.
- **Log *output* is data, not code** — `.log` files go to a top-level `logs/` folder (git-ignored), never in `src/`.

**Debug output style — structured, organised, neat, yet simple and elegant.**

- **NEVER use emoji. Ever.** Not in logs, not in output, not in commit messages, not anywhere.
- Use **inline colored text** (ANSI color codes) to structure and highlight output — e.g. green for success/completed, yellow for warnings, red for errors, dim/grey for detail, bold for headers. Color carries the meaning that emoji would otherwise; it stays clean, professional, and terminal-native.
- Keep it readable: aligned columns, clear labels, consistent phrasing. Elegant means *less* — enough structure to scan at a glance, no clutter.

### Config — central, but sectioned by area

**Config is centralised in one place, but organised into sections by the area that uses it** — never one giant flat file. This is one-file-one-job applied to settings: each config section holds only the settings for its own domain and sits next to the concept it configures.

- Config lives in a `src/config/` package, one file per area of the system:
  - `config/broker.py` — API URL, username, API key, account settings
  - `config/data.py` — default symbol, timeframe, bar limits
  - `config/backtest.py` — starting capital, commission, slippage
  - `config/live.py` — poll interval, live-vs-sim flag
  - `config/risk.py` — max risk per trade, max open positions, loss limits
  - `config/logging.py` — log level, log directory
  - (add a new section file when a new area appears — don't dump it into an existing one)
- **Each caller imports only the section it needs** (`from src.config import risk`), same who-needs-what rule as everything else. The backtest never imports `live`; the risk engine never sees API keys.
- **`config/__init__.py` loads `.env` once** (`load_dotenv()`) at the package front door, so every section reads secrets via `os.getenv()` without repeating it.
- **Secrets vs settings — one hard line:**
  - **Secrets** (API keys, passwords, usernames) live ONLY in a top-level `.env` file, git-ignored, **never committed**. Config sections read them with `os.getenv()`.
  - **Settings** (limits, symbols, capital, log level) live in the `config/*.py` files and ARE committed — they're not sensitive.
- **Never hard-code a value that might change** (keys, limits, symbols, URLs, intervals) into logic. Put it in the right config section and import it — one source of truth, changed in one place.
- Config holds the *value* of a dial (e.g. `config/logging.py` sets the log level); the module that *applies* it (e.g. `logging_config.py`'s `setup_logging()`) reads that value. Keep the setting and the code that acts on it separate.

### Interface: CLI-first

For now this is a **CLI-driven, Python-only project** — the primary interface is a command-line tool, no frontend yet. Keep the CLI entry point under `src/` (e.g. `src/cli/`).

```
algo_3/
├── src/               ← Python backend (engine, strategies, API, CLI)
│   ├── backtest/
│   ├── strategy/
│   ├── cli/           ← command-line interface (primary interface for now)
│   └── api/
├── data/
└── requirements.txt
```

### Frontend (future — only when JS is added)

A JS/TS frontend may come later. **When** it does, it gets its own self-contained top-level `frontend/` folder (its own `package.json`, build tools, dependencies, and internal JS/TS `src/`). Never put JS/TS app code inside the Python `src/` — keep the two worlds cleanly separated. Until then, don't scaffold a `frontend/` folder.

## Commands documentation

**Every runnable command goes in the top-level `COMMANDS.md`.** Jake should never have to guess how to run anything.

- Any time a command is added, renamed, or changed in any way — a new CLI entry point, a script, a make/task target, a one-off invocation — **write it in `COMMANDS.md` in the same commit** as the code change.
- Each entry states the exact command (runnable from the repo root) and a one-line description of what it does.
- Keep it current: if a command is removed, delete its entry. `COMMANDS.md` is the single source of truth for "how do I run this."

## Project maps — two of them, kept current

**The project is described by two maps, and they must never blur together.** Everything in the project exists in both at once; keeping them separate is what keeps the codebase understandable.

- **The code map (`ARCHITECTURE.md`)** — how the *files* are wired: the folder tree and who-imports-who (the dependency graph). It answers "if I open this cold, how does it fit together, and where do I run it?"
- **The domain map (`GLOSSARY.md`)** — what the project is *about*: plain-English definitions of the trading concepts (account, contract, bar, order, position). Each concept is a **thread** traced through its layers — config (which/how much) → code (does it) → API endpoint (serves it) → doc (explains it).

Rules:

- **A domain word is not a code word.** "Contract" means a tradeable futures instrument (a trading concept); `broker/contracts.py` is the code file whose job is to handle contracts. Never conflate the concept with the file that deals with it.
- **Keep both maps current in the same commit** as the change. Add/move/rename a module or change its imports → update `ARCHITECTURE.md`. Introduce a new domain concept → add its definition and thread to `GLOSSARY.md`.
- **The organizing principle is fractal** — one job, and a small map of its parts, at every zoom level: project → folder → file → function. A folder's map is its files; a file's map is its import block + function list; a function's map is the calls inside it. Read any unfamiliar file by asking: what does it import (attach), what does it define (jobs), what does the `__main__` guard run (the door)?
- **The `projectX_API/` docs are the API map** — `projectX_API/README.md` is the index (every endpoint → its detail file); the individual `.md` files hold one endpoint each (one file = one job). Don't flatten them; link to them from `GLOSSARY.md`.

## Version control workflow

**Commit after every change.** Any time code is written, edited, created, moved, or deleted — or any file is otherwise changed — make a git commit for it.

- Commit immediately after each change is complete. Do not batch unrelated changes into one commit.
- Write a clear, concise commit message describing what changed and why.
- **Do NOT push.** Only push when Jake explicitly says to (e.g. "push", "push it").
- Remote: `origin` → https://github.com/Jakers471/algo_3.git
