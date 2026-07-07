# CLAUDE.md

## Project structure

**All code lives under `src/`. Keep `src/` clean.**

- The top level is for config, docs, dependency lists, and git files only — things like `CLAUDE.md`, `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env`. Keep these out of the way and out of `src/`.
- Every source file you write, create, or move goes under `src/` (in an appropriate subpackage). Do not put code at the top level.
- Reference/data directories (e.g. `projectX_API/`, `data/`) are not code and stay at the top level, not in `src/`.

### One file = one job

**Each file does one job — it has one reason to exist and one reason to change.** This keeps the codebase clean, organised, and easy to understand, build on, and debug.

- Before writing a line, name what it *does* ("this logs in", "this fetches bars", "this calculates Sharpe"). The verb tells you the file. If a line doesn't fit any existing file's job, that's a new file.
- Split by **who needs what**. If two callers need different parts of a file, those parts belong in separate files so each caller imports only the half it needs (e.g. `broker/client.py` for the shared connection, `broker/history.py` for bars, `broker/orders.py` for order actions).
- Separate **plumbing from logic**. Code that talks to the outside world (API calls, file read/write) stays apart from your actual decision logic (strategy, backtest math), so logic can be tested without touching the API.
- **Keep interface files thin.** A CLI command or `main.py` just parses input, calls the real function in a module, and formats the result — it holds no trading logic itself. The weight lives in the modules; the doors on top stay feather-light.
- **Split when it hurts, not before.** It's fine to start with one file and break it apart the moment a second caller needs only part of it. Don't over-plan the structure up front — let the seams reveal themselves and refactor toward one-job-per-file as they do.

### Logging & debug

**Use Python's `logging` module, never bare `print`, for all debug/progress output.** `logging` has levels you can dial up or down without deleting code; `print` is permanent noise.

- **Log calls go inline** in the `.py` file doing the work — a `logger.info("completed X")` narrates the job it sits next to. This does not violate one-file-one-job; a log line reports on the file's existing job.
- Use levels deliberately: `logger.debug()` for noisy detail (bug hunting), `logger.info()` for normal "completed / doing" progress, `logger.warning()` / `logger.error()` for problems. Set level to `DEBUG` while debugging, `INFO` when running normally — no lines get deleted.
- **Log *configuration* is its own job** — format, level, and destinations live in one module (e.g. `src/logging_config.py`) with a `setup_logging()` called once at startup by the CLI/`main.py`. Change format or add a log file in that one place; every module follows.
- Each module gets its logger with `logger = logging.getLogger(__name__)` at the top. Modules decide *what* to log; `logging_config.py` decides *how and where*.
- **Log *output* is data, not code** — `.log` files go to a top-level `logs/` folder (git-ignored), never in `src/`.

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

## Version control workflow

**Commit after every change.** Any time code is written, edited, created, moved, or deleted — or any file is otherwise changed — make a git commit for it.

- Commit immediately after each change is complete. Do not batch unrelated changes into one commit.
- Write a clear, concise commit message describing what changed and why.
- **Do NOT push.** Only push when Jake explicitly says to (e.g. "push", "push it").
- Remote: `origin` → https://github.com/Jakers471/algo_3.git
