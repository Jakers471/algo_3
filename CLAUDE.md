# CLAUDE.md

**This file holds timeless *rules* only.** It is always loaded into memory, so it must never contain point-in-time snapshots — folder trees, file lists, current command sets — that drift out of date and then mislead every session. The live structure lives in `ARCHITECTURE.md` (the code map) and `commands.bat` (the runnable command menu — how to run things), which are updated in the same commit as any change. Rules here; current facts there.

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
- New areas get their own labeled folder as they arrive. For the current set of folders, see `ARCHITECTURE.md` — it is not listed here (snapshots go stale).

### One file = one job

**Each file does one job — it has one reason to exist and one reason to change.** This keeps the codebase clean, organised, and easy to understand, build on, and debug.

- Before writing a line, name what it *does* ("this logs in", "this fetches bars", "this calculates Sharpe"). The verb tells you the file. If a line doesn't fit any existing file's job, that's a new file.
- Split by **who needs what**. If two callers need different parts of a file, those parts belong in separate files so each caller imports only the half it needs (e.g. `broker/client.py` for the shared connection, `broker/history.py` for bars, `broker/orders.py` for order actions).
- Separate **plumbing from logic**. Code that talks to the outside world (API calls, file read/write) stays apart from your actual decision logic (strategy, backtest math), so logic can be tested without touching the API.
- **Keep interface files thin.** A CLI command or `main.py` just parses input, calls the real function in a module, and formats the result — it holds no trading logic itself. The weight lives in the modules; the doors on top stay feather-light.
- **Split when it hurts, not before.** It's fine to start with one file and break it apart the moment a second caller needs only part of it. Don't over-plan the structure up front — let the seams reveal themselves and refactor toward one-job-per-file as they do.
- **A compound request is not a request for one script.** When Jake bundles several actions in one breath — "connect to ProjectX, grab accounts, fetch NQ data", or "x, y and z", or "this, this and that" — that is a list of *separate jobs*, each getting its own file, even though he didn't say "split it up." This is a trading algorithm built from many small, modular pieces; default to modularity. When in doubt, split.
- **Never duplicate logic.** If something already exists, reuse it — import the existing file, don't rewrite it. When Jake reiterates "I need you to build X" and we already have X (or a piece of it), do NOT re-create it; extend or call what's there. Every file is reusable and pluggable: written once, imported everywhere. Duplicated logic is a bug.

### Scratch vs permanent

**`src/` is the permanent, committed codebase; `scratch/` is a git-ignored working area for experiments, one-off tools, and analysis. Decide which a file is before writing it.**

- **The placement test:** ask *"is this part of the product — a job the system does repeatedly?"* If yes → `src/` (permanent, modular, maintained). If it's exploration, a one-off, an analysis, or a tool you're not sure about yet → `scratch/`.
- **`src/` is permanent-only.** If code lives in `src/`, it's a commitment to keep and maintain it. Never write a throwaway experiment in `src/`.
- **`scratch/` is NOT auto-throwaway.** It's git-ignored and outside the product, but code there **persists and may have ongoing use** — a comparison you re-run, an audit generator, a tool you come back to. **Nothing in `scratch/` is deleted unless Jake specifically says so.** Do not remove a scratch file just because its immediate job is done. Never import `scratch/` from `src/`.
- **When a scratch file earns a permanent place, graduate it.** If an experiment becomes something the product relies on, *promote* the reusable part into a proper `src/` module (strip the throwaway bits). Promotion is additive — it does not require deleting the scratch original unless Jake says so.
- **Deleting an orchestrator never deletes its engine.** A thin door (e.g. `cli/connect.py`) can be removed once its purpose is served; the `broker/` modules it called are separate and stay. Kill the door, keep the engine.
- **A disclosed throwaway job may be ONE condensed script.** The modular rules (one file = one job, folders by category, thin doors) govern *permanent* `src/` code. When Jake explicitly discloses a task is a one-off, write it as a single self-contained script in `scratch/` rather than splitting it across modules — modularity buys nothing for a one-off; condensing is faster and just as correct. Applies ONLY on explicit disclosure and ONLY in `scratch/`; never condense permanent `src/` code this way.
- **NEVER run-then-delete.** After running a scratch script, leave it in place. Deletion is always Jake's call — he needs to run it and see the raw output himself first. Show him the results, then *wait* for an explicit go-ahead before deleting. A summary is not a substitute for him seeing it. When in doubt, keep the script.

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

For now this is a **CLI-driven, Python-only project** — the primary interface is a command-line tool, no frontend yet. Keep the CLI entry point under `src/` (e.g. `src/cli/`). The live folder layout is not drawn here; see `ARCHITECTURE.md`.

### Frontend (future — only when JS is added)

A JS/TS frontend may come later. **When** it does, it gets its own self-contained top-level `frontend/` folder (its own `package.json`, build tools, dependencies, and internal JS/TS `src/`). Never put JS/TS app code inside the Python `src/` — keep the two worlds cleanly separated. Until then, don't scaffold a `frontend/` folder.

## Commands — the runnable menu (`commands.bat` + `commands.ps1`)

**The command hub is a runnable arrow-key menu, not a doc.** Jake double-clicks `commands.bat` (a thin launcher); it opens the menu defined in `commands.ps1`. Navigate with Up/Down, Enter to select, Esc to go back or quit. Selecting a command runs it. The hub is *runnable*, not a passive list to copy from.

- **`commands.bat` is a thin door** — it only launches `commands.ps1`, no logic. All labels, structure, and dispatch live in the `commands.ps1` menu tree.
- **The menu is a nested tree, grouped by labeled category** (Setup, CLI / Workflows, Data, …). A category is a submenu; menus nest freely. Add a new category submenu when a new area of commands appears; never pile unrelated commands under one heading.
- **Every runnable command is a menu item** in the tree — either `@{ Label='...'; Run={ <command> } }` (runs it) or `@{ Label='...'; Submenu=@{...} }` (nests). Wire a new command into the tree in the *same commit* as the code that adds it.
- **Items dispatch to the real command** (e.g. `Run = { python -m src.cli.<name> }`); the menu holds no trading logic, just labels and calls.
- **Always updated, always cleaned** — add/rename/change a command → update its item; remove a command → delete its item. No dead menu items, ever.
- **Wire in EVERYTHING runnable Jake will re-run — including persistent `scratch/` tools.** `src/` commands, workflows, AND scratch tools (audits, generators, comparisons) all get a menu item, added in the *same commit* you create them. Only a genuine one-shot spike (run once, never again) is exempt. **Whenever you build something runnable, wiring it into the menu is part of the job, not an afterthought — do not finish a runnable tool without giving Jake a way to run it here.**

## Project map — the code map, kept current

**`ARCHITECTURE.md` is the code map** — how the *files* are wired: the folder tree and who-imports-who (the dependency graph). It answers "if I open this cold, how does it fit together, and where do I run it?"

- **Keep it current in the same commit** as the change. Add/move/rename a module or change its imports → update `ARCHITECTURE.md`.
- **A domain word is not a code word.** "Contract" means a tradeable futures instrument (a trading concept); `broker/contracts.py` is the code file whose job is to handle contracts. Never conflate the concept with the file that deals with it. Definitions of the trading concepts themselves live in the `projectX_API/` docs — don't re-document them in the codebase.
- **The organizing principle is fractal** — one job, and a small map of its parts, at every zoom level: project → folder → file → function. A folder's map is its files; a file's map is its import block + function list; a function's map is the calls inside it. Read any unfamiliar file by asking: what does it import (attach), what does it define (jobs), what does the `__main__` guard run (the door)?
- **The `projectX_API/` docs are the API map** — `projectX_API/README.md` is the index (every endpoint → its detail file); the individual `.md` files hold one endpoint each (one file = one job). Don't flatten them.
- **No separate domain glossary for now.** The vocabulary is small and already defined in `projectX_API/`. If the domain vocabulary grows large enough that terms are constantly re-looked-up, revisit — split when it hurts, not before.

## Markdown docs (the "mds") — keep them consistent

**When Jake says "mds" (or "the markdown files" / "the docs"), he means every project markdown file EXCEPT `CLAUDE.md` — check them all and make sure they agree.** These docs are one connected reference and must never contradict each other.

- **Keeping the mds current is AUTOMATIC.** Every code change checks the mds (except `CLAUDE.md`) and updates any the change affects — in the *same commit*. Don't wait for Jake to say "mds". A change that touches no doc needs no update; use judgment. **The one exception is `scratch/`-only work:** editing or adding scratch files needs no docs pass and no project audit — scratch is git-ignored and outside the product, so it can't drift the mds. (If scratch work also touches committed files — e.g. wiring a tool into `commands.bat` — that committed part still follows the rule.) This generalizes the "keep `ARCHITECTURE.md` current" and "wire `commands.bat` in the same commit" rules — the whole mds set must always match reality.
- **`CLAUDE.md` is locked and separate.** It is rules only, and it is NOT part of "mds." Never read or edit `CLAUDE.md` on an "mds" request — touch it only when Jake explicitly names *CLAUDE.md* and tells you to read or update it.
- The "mds" set is the project's *other* `.md` files: `README.md`, `ARCHITECTURE.md`, `DATA_AUDIT.md`, and per-folder `README.md`s (`data/`, `scratch/`). (`projectX_API/*.md` are external API reference; `venv/` docs belong to dependencies — neither is ours to reconcile.)
- On an "mds" request, review them **overall** (no doc contradicts another; conventions match) and **specifically** (the exact thing Jake changed is reflected everywhere it appears), and reconcile any drift in the same pass.
- When a shared fact changes, update every "mds" that mentions it in the same commit — never leave one saying the old thing.

## Version control workflow

**Commit after every change.** Any time code is written, edited, created, moved, or deleted — or any file is otherwise changed — make a git commit for it.

- Commit immediately after each change is complete. Do not batch unrelated changes into one commit.
- Write a clear, concise commit message describing what changed and why.
- **Do NOT push.** Only push when Jake explicitly says to (e.g. "push", "push it").
- Remote: `origin` → https://github.com/Jakers471/algo_3.git
