# CLAUDE.md

## Project structure

**All code lives under `src/`. Keep `src/` clean.**

- The top level is for config, docs, dependency lists, and git files only — things like `CLAUDE.md`, `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env`. Keep these out of the way and out of `src/`.
- Every source file you write, create, or move goes under `src/` (in an appropriate subpackage). Do not put code at the top level.
- Reference/data directories (e.g. `projectX_API/`, `data/`) are not code and stay at the top level, not in `src/`.

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
