# Systematic Strategy Research Workflow

A funnel for taking trading ideas from "I see a pattern" to a live/dead verdict,
ordered so the cheapest tests kill things first. Every idea — chart intuition,
literature effect, microstructure hunch — enters the same way and is judged by
the same standards. The output of the process is not strategies; it is
**verdicts**: validated edges, honest corpses, and a ledger that stops you from
re-mining either.

Core principle: an equity curve is the *last* thing you look at, not the first.
A backtest is signal x entry x exit x sizing x costs multiplied together; when
the curve looks good you don't know which factor did it, and when it looks bad
you don't know which factor broke it. The funnel isolates one factor at a time.

---

## Stage 0 — Pre-registration (before touching data)

Write a frozen brief containing:

- **The hypothesis, singular.** One mechanism, stated in plain language.
  The best filter available: *who is on the other side of this trade, why are
  they transacting at a bad price, and why can't they stop?* If the idea can't
  name its counterparty or mechanism, it's a chart pattern in a suit.
- **Exact definitions.** Every window, level, session boundary, and convention
  nailed down (timezones, DST, half-days, roll handling). "Wait for a strong
  range" is not a definition; "snapshot at 11:00 ET" is.
- **Kill criteria, pre-committed.** What numbers count as dead — typically:
  episode-level t < 2 on the recent era, mean below a floor that clears costs,
  concentration above a ceiling. Decided *before* results exist, never moved
  after.
- **Explicit out-of-scope list.** The sweeps you are not allowed to run.
  Anything interesting found outside the pre-registered questions goes to
  QUARANTINE.md as a new hypothesis — it is never reported as a finding.
- **Parameter budget.** A decade of daily data supports maybe 3–5 fitted
  parameters total. Prefer conventions (70% VA, month-end, 14:00 ET) and
  ensembles/continuous sizing over tuned thresholds. Every knob added later
  must buy its keep with fresh out-of-sample evidence.

Rules:
- One hypothesis per brief where possible. Clock/calendar families are
  multiple-comparisons minefields — pre-specify the two or three effects with
  documented priors and test only those.
- Revisits of killed families are allowed, but only through a **new** stage-0
  brief attacking what the autopsy diagnosed. The parent verdict never reopens.

## Stage 1 — Causality audit

Verify every input at time t is computable at time t:
- Higher-timeframe data shifted one full bar before as-of alignment.
- No same-bar peeking on triggers; signals stamped at completed-bar closes.
- Session boundaries, DST, half-days handled via exchange calendar.
- Event times genuinely ex-ante (scheduled calendars only).

Every output must include a written no-lookahead audit paragraph. This is the
single most common way beautiful backtests are fake.

## Stage 2 — Conditional forward returns (the signal test)

No strategy. No entries, exits, stops, sizing, or costs. For every bar (or
event): record the signal state, record raw forward returns at 2–3 fixed
horizons, compare distributions across states.

Answers exactly one question: **does knowing the signal sort the future at
all?** Most ideas die here, in an afternoon, at zero drawdown.

Report per state: n, mean (bps), median, hit rate, t-stat, and the full
distribution shape (a long-vol strategy *should* show ~40% hit rate with a fat
right tail — pre-register the expected shape so you recognize health vs
sickness).

**Critical lesson (paid for):** if the eventual entry is stop-style, measure
from the *achievable* price, not the level price. On trend days price gaps
through levels; the level-to-market distance is a different entry price, not
slippage, and crediting it manufactures phantom edge.

## Stage 3 — Robustness within sample

- **Era split** (e.g., first half vs second half of history; align one boundary
  with any relevant publication date). The default failure mode is an effect
  that lives in one regime only. An effect that *strengthens* in the recent era
  is the good sign; one that only exists recently is a different, fragile
  object requiring a named structural driver to keep.
- **Shape sanity.** Monotonicity with signal intensity is mild extra evidence —
  remember nested thresholds share observations, so a smooth staircase is
  partly mechanical.

## Stage 4 — Effective sample size (the honest n)

Count independent **episodes** (contiguous signal runs, or discrete events),
not bars. Recompute t on that n. Report **top-5 episode share** of total P&L.

- 1,600 clustered bar-signals can be 80 episodes; five of them can carry >100%
  of the P&L (meaning the rest net lose). That is a lottery ticket wearing an
  edge's costume.
- Concentration ceiling is a kill criterion, not a footnote.

## Stage 5 — Out-of-sample, once, frozen

One correlated-but-different instrument and/or a held-out period. Settings
untouched. Result logged either way. One shot — re-tweaking after seeing it
contaminates it permanently (you are silently back at stage 0 with a spent
bullet).

Honesty check: if the OOS instrument is ~0.9 correlated and the episodes fall
on the same dates, it is the same experiment in a different wrapper — it rules
out instrument-specific artifacts but does not double the evidence. Report the
episode date-overlap.

## Stage 6 — Costs and fills, measured not assumed

- Spread + commission modeled pessimistically; better, **measured from tick
  data at the exact times the strategy trades** (spreads blow out precisely
  when event strategies trade; stops fill at the worst moments by
  construction).
- Stop entries: simulate against the tape with a conservative queue assumption
  (never part of the trigger print; next print, adverse-side quote, never
  better than the level). Report the fill distribution, not its mean — the
  worst fills correlate with the best trades' moments.
- Limit entries: nearly assumption-free fills, but the risk moves to adverse
  selection (filled exactly when the level is being steamrolled) — measure
  that instead.
- Sanity-check the thermometer in both directions: a 70-tick mean slip on a
  top-liquidity contract is a broken measurement (stitched-roll tape defects,
  point-costs applied across eras of very different price levels), not a
  market fact. Fixing a broken measurement after seeing results is allowed if:
  it is one disclosed fix, in the direction the evidence forces, with kill
  criteria untouched, and both runs' outputs preserved.
- If the verdict is Monte Carlo–based and lands near the kill line, run a
  seed-robustness sweep and record the spread. "Killed by 0.1 bps, seed-robust"
  is a complete sentence; "killed by 0.1 bps on seed 0" is not.

## Stage 7 — Strategy construction (survivors only)

Exits, sizing, stops — added one at a time, downstream of a surviving signal,
each owing its own out-of-sample evidence. Never used to rescue anything that
failed stages 2–6. Performance must sit on a plateau, not a spike: perturb
every parameter and expect graceful degradation.

Sizing derives from the measured worst episode, not the average. Vol-scaled
position sizing (constant risk; size down as vol-rank rises) is one of the few
overlays with documented support and near-zero knobs — default to it.

---

## The ledgers (the real IP)

Maintain three files. They are why the process compounds.

**LEDGER.md** — one entry per completed brief, final, reopenable only via a new
stage-0 brief. Record: hypothesis, spec pointer, headline numbers, which stage
killed it (or "validated"), the epitaph in one honest paragraph, and pointers
to every artifact (logs, PNGs, commits). Include the marginal calls ("dead
under the rule, not obviously dead in nature"). Possible verdicts:
- **Validated — trading.**
- **Validated — declined** (real edge, incompatible with constraints; a mature
  ending, not a failure).
- **Killed** (with the stage and the number).
- **True but unmonetizable** (real fact, no accessible trade — e.g., an
  overnight premium eaten by twice-daily costs; still valuable as context).

**QUARANTINE.md** — every interesting thing noticed outside a pre-registered
question. Each entry is a hypothesis awaiting its own stage-0 brief, never a
finding. This file is where "just check one variant" goes to wait its turn
instead of contaminating the current run.

**Negative results are assets.** "This instrument has no unconditional intraday
drift" and "stop entries cannot collect breakout continuation here" are
permanent, reusable knowledge that sharpen every future test's bar.

---

## Working with a quant (human or AI)

- Briefs are delivered frozen and verbatim; the quant runs them as written.
- The quant is expected to **refuse to reconstruct a "pre-registered" brief
  from memory** — no written spec, no run.
- The quant flags untested variants in its own output ("NOT tested here") and
  holds that boundary when a reviewer's summary drifts past it. Reviewers err;
  outputs' own caveat lines are the guardrail.
- Measurement fixes after first results: allowed under the stage-6 conditions
  above (one fix, disclosed, evidence-forced, criteria untouched, both runs
  preserved). Spec changes are not.
- Kill lines for any mid-stream follow-up are written down **before** the run
  completes, in the ledger, so pre-registration under time pressure never
  becomes post-hoc labeling.
- Read whipsaw/worst-case accounting **last** — it is ugly by construction and
  the pre-registration only holds if nobody negotiates with it.

---

## Priors to calibrate against (so results are read sanely)

- Most ideas die. On heavily-mined instruments, price-transform signals dying
  6-for-6 is the base rate working, not the method failing. Non-price
  information sources (event calendars, order flow) carry better priors.
- Published anomalies decay after publication — test the post-publication era
  as the verdict, not the full sample.
- "True about prices" ≠ "collectible by you." Expect a large gap between
  gross-at-level and achievable; measure it every time.
- Faint edges stack. The goal of a single test is a *tile* — small, real,
  uncorrelated — not a jackpot. Combine tiles across genuinely different
  sources (trend, calendar, flow, vol-sizing), equal-weighted; optimized
  combination weights are knobs sneaking back in.
- The eye is a pattern detector with no significance test. Charts are for
  hypothesis generation (stage 0) and debugging — the moment a pattern is
  coded, stop looking at the picture.
- Sequencing is by information-per-hour: cheap decisive tests before expensive
  ambiguous ones. Suggested idea-source order: event/calendar effects with
  documented mechanisms → structural flow effects → microstructure (with
  measured costs) → price transforms (worst priors, test last if at all).

## Failure modes this workflow exists to catch

| Disease | Symptom | Stage that catches it |
|---|---|---|
| Lookahead | too-beautiful curve | 1 |
| No signal | states don't sort returns | 2 |
| Regime mirage | effect lives in one era | 3 |
| Clustered n | huge bar-count t, tiny episode t; top-5 share >50% | 4 |
| Settings-fitted | dies on frozen OOS | 5 |
| Phantom fills / cost-fragile | gross survives, achievable/net doesn't | 6 |
| Knob rescue | parameters added to fix a corpse | 7 (forbidden) |
| Data snooping | many implicit hypotheses, one "winner" | 0 (budget) + quarantine |

---

*The process in one line: pre-register the question, let the cheapest honest
number answer it, write the verdict down, and never negotiate with a result —
in either direction.*
