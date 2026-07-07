# CLAUDE.md

## Project structure

**All code lives under `src/`. Keep `src/` clean.**

- The top level is for config, docs, dependency lists, and git files only — things like `CLAUDE.md`, `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env`. Keep these out of the way and out of `src/`.
- Every source file you write, create, or move goes under `src/` (in an appropriate subpackage). Do not put code at the top level.
- Reference/data directories (e.g. `projectX_API/`, `data/`) are not code and stay at the top level, not in `src/`.

### Backend vs. frontend

`src/` is **Python only**. The frontend is a separate world and gets its own top-level `frontend/` folder — self-contained, with its own `package.json`, build tools, dependencies, and its own JS/TS `src/` inside it. Never put JS/TS app code inside the Python `src/`.

```
algo_3/
├── src/               ← Python backend (engine, strategies, API)
│   ├── backtest/
│   ├── strategy/
│   └── api/           ← serves data to the frontend
├── frontend/          ← the whole JS/TS app, self-contained
│   ├── src/           ← its own src, in JS-land
│   ├── package.json
│   └── ...
├── data/
└── requirements.txt
```

Keep the two worlds cleanly separated: `src/` stays purely Python, `frontend/` stays purely JS/TS. The Python API layer (`src/api/`) is what serves data to the frontend.

## Version control workflow

**Commit after every change.** Any time code is written, edited, created, moved, or deleted — or any file is otherwise changed — make a git commit for it.

- Commit immediately after each change is complete. Do not batch unrelated changes into one commit.
- Write a clear, concise commit message describing what changed and why.
- **Do NOT push.** Only push when Jake explicitly says to (e.g. "push", "push it").
- Remote: `origin` → https://github.com/Jakers471/algo_3.git
