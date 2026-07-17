# session_history — the population, the seal, and the readings built on both

This package is the research backbone under `session_stats`: everything that
answers "how does *this* session compare to every session before it," and the
discipline that keeps those answers honest.

## The parts, in dependency order

| file | job |
|---|---|
| `split.py` | read the committed seal (`SESSION_SPLIT.json`, repo root) and label any session `explore` or `sealed`. The ONE place the boundary is enforced. |
| `catalog.py` | walk a dataset once through the real indicators and write one parquet row per bar of every London/NY session — the card as a population, not an anecdote. |
| `build.py` | reduce cumulative range/travel/volume per elapsed bar to percentile breakpoints — the compact table `session_stats`' percentile fields read live. |
| `store.py` | load that table; answer `percentile_rank()` / `travel_budget()` at runtime. |

Doors: `python -m src.cli.session_catalog` and `python -m src.cli.session_history`
(both in `commands.bat` → Data). The seal itself is written once by
`scratch/session_research/seal_split.py` — deliberately NOT in the menu, because
re-running it would move the cutoff, and a cutoff that moves is not a seal.

## The seal

Two artifacts, one boundary, checked against each other on every load:

- **The declaration** — `config/session_history.py`'s `SEALED_FROM`, a round
  date near the two-thirds mark (2025-10-01), deliberately not tuned: tuning
  it would itself be a look at the vault.
- **The receipt** — `SESSION_SPLIT.json` at the repo root, frozen and
  committed like `DATA_AUDIT.json`, recording exactly which sessions that
  declaration seals: counts, spans, the rule. Sessions starting on or after
  the date are `sealed` (817 explore / 395 sealed on the shipped NQT 5m).

`split.py` refuses to answer if the two disagree (`SealDrift`), so neither can
move quietly. Time, not random, because volatility clusters — a random split
leaks, a day in explore informing the day beside it in test. A committed file,
not a seed, because a seed can drift silently and a committed file cannot.

**Sealed sessions are not looked at.** Not plotted, not eyeballed, not "just
checked." They exist for exactly one purpose: the single honest evaluation of
a rule that is already frozen. Every look before that spends them, permanently.
The catalog enforces this by construction — its default build writes explore
rows only, and sealed rows go to a separate, loudly-named file that only
`--include-sealed` produces.

## The order of operations, and why it is the whole point

Everything that costs **zero** degrees of freedom happens before anything that
costs one:

1. **Seal** — done first because it is the only step that gets worse every day
   it waits; every session eyeballed before sealing is already spent.
2. **Catalog** — description is free. ~65k explore rows replace N=1 anecdotes.
3. **Interrogate** — distributions, joint distributions, keyed on
   session-elapsed-bars. Reports, not rules. Still free.
4. **Only then, a signal** — k-NN over the catalog before any rule system:
   ~one parameter instead of ten. If k-NN finds nothing, a ten-parameter rule
   "finding" something is almost certainly fitting noise.

## Known debts, recorded rather than hidden

- The **N study** (`scratch/session_research/session_window_study.py`, chose N=6) was
  computed over ALL 1,212 sessions — including what is now sealed — before the
  seal existed. That leak is spent and cannot be unspent; it is the mildest of
  these, because the study fit N to **event counts, not returns**. Re-run it on
  explore only before any evaluation on sealed data.
- The **percentile table** carried the same debt, and no longer does: the two
  populations are now separate files that cannot overwrite each other
  (`NQT_5m_full.npz`, `NQT_5m_explore.npz`), each stamped with what it was
  built from. Build both with and without `--explore-only`; ask a table which
  it is with `store.describe(symbol, timeframe, split_label)`. The gap this
  closed was never "can you scope it" — `--explore-only` already worked — but
  "can you know what you scoped," and the two tables genuinely differ: NY at
  bar 20, range 3.0 x range_scale ranks at the 3.3rd percentile against full
  history and the 2.8th against explore.
- The sessions eyeballed during development (NY 25 Jun '26 among them) fall in
  the sealed period and are burned as evaluation material.
- The catalog deliberately omits the percentile fields: they are derived FROM
  the distribution the catalog holds raw, and the shipped table's full-dataset
  provenance would leak the vault's shape into explore rows.
