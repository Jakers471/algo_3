# session_stats — phase definition and build order

Context for the two open questions. Answers first, reasoning after.

## Why this is changing at all

The session card computes every stat open-to-now. That silently fails on any
session with more than one character, and it failed on a real one (NY, 25 Jun '26):
a near-vertical crash followed by a base at the lows.

- `efficiency 0.33` was the blend of a ~1.0 impulse and a ~0.1 consolidation.
  It described neither. It read as "choppy grind"; the session was a violent
  directional collapse.
- `direction changes 16` came almost entirely from the base. The crash
  contributed ~0.
- `delta -3.0K on 211.4K volume` was the worst one. It read as "no aggressive
  selling behind the decline." The selling was plainly there — it got **cancelled**
  by dip-buying at the lows. A cumulative sum across opposing regimes does not
  average, it cancels.

Aggregates over a bimodal session don't return an error. They return a
plausible-looking number pointing the wrong way.

## Q1: Phase definition — option 1, with a modification

**Fixed rolling window. Not regime, not swing/legs.**

- **Not option 2 (regime).** Explicitly off the table. `indicators/regime.py` is
  not considered complete or validated, and its cutoffs were tuned for a
  different purpose. Do not couple `session_stats` to it.
- **Not option 3 (swing).** Legs/swing are a dependency Jake doesn't want here
  yet. This system is deliberately standalone.

**The modification: it's two adjacent windows, not one lookback.**

A single trailing window of N bars gives a stat but no way to know the character
just changed. Use **two adjacent sliding windows** — `recent` = last N bars,
`prior` = the N before that — recomputed every bar. The *comparison between them*
is the phase-change detector. You don't need to detect a phase boundary; the
difference between the windows already is one.

Sliding, not tumbling. Fixed non-overlapping blocks reintroduce the exact
blending bug at arbitrary cut points — a transition landing mid-block gets
averaged the same way the session card averaged it.

### The rule that decides how each stat is compared

Split the fields by whether they carry units:

- **Dimensionless already** — efficiency (range/travel), direction-change *rate*
  per bar, net-over-range, close-in-range. Points cancel in the formula. Read
  these per window and compare with plain subtraction. No ruler, no calibration.
- **Dimensioned** — range, travel, volume, delta. A raw number here rots over
  time (NQ's median 30s range moved 4.50 -> 14.25 across 29 months, a 3.17x
  drift; this is why `swing.py` bans point thresholds). These may **only** appear
  as a **ratio between the two windows** — `range_recent / range_prior` is
  dimensionless even though neither term is.

Consequence: **no field in this indicator needs an absolute threshold in points,
ever.** The ratio makes the ruler divide out. This is why the two-window design
is structurally better than absolute cutoffs, not merely simpler.

### The signature this is built to find

Impulse, then base, drying up — i.e. the breakout setup:

    efficiency_prior      high
    efficiency_recent     low
    range_recent / range_prior    << 1
    volume_recent / volume_prior  < 1

The **bias** then comes from `net` of the *prior* window — the phase that
actually had conviction — instead of from a session average that cancelled it.

### Choosing N

With ratios, N is no longer a calibration that can be wrong in points. It's a bet
on the minimum phase duration worth detecting. The pair acts as a bandpass
filter: it sees transitions whose duration is comparable to N. Too long and both
windows straddle the transition, the ratio goes to 1, and it's blind to the exact
event it exists for. Too short is noise.

So **don't pick one.** Run a small geometric ladder — N, 2N, 4N — and let the
shortest rung that fires report the scale the phase happened at. Three copies of
one computation, and no specific number to defend.

Prior art on how to set a dial like this, if needed: `swing.py`'s RETRACE was not
chosen for correctness. `scale_ladder.py` measured H = 0.503 — swing count obeys
the random-walk law, so **there is no privileged scale and no "true" window to
find.** It was chosen for event count (sqrt(n) power) and freshness. Set N the
same way — by measuring events produced and lag, **never by optimizing PnL**,
which will overfit a single parameter into oblivion.

### Phase age

**Drop the field.** With a sliding window there is no discrete phase, so
`phase age` has no referent, and "bars since range last expanded past X"
smuggles a point threshold back in — the thing the ratio design just removed.

The window ratios already carry what phase age was wanted for. If it's still
wanted later, define it internally as *bars since the contraction signature
became true* — derived from the windows themselves, no external dependency.

### Optional upgrade (not required for v1)

Make the windows **equal-volume rather than equal-time**. Thirty minutes of that
crash and thirty minutes of the base are not comparable units of market activity;
50K contracts and 50K contracts are. The crash gets carved finely and the base
coarsely, automatically. Needs only volume — no new dependency.

## Q2: Build order — option 1, correctness first

Ship the cuts and the delta fix now. Everything else follows once the phase
definition is proven.

**Now:**

1. **Cut body / up-wick / low-wick.** This is provable, not a judgment call.
   They are fully determined by `net % of range` and `closed at % of range`, two
   lines directly above them. From the same card: close at 39%, net -48%, so open
   sat at 39+48 = 87%. body = |net| = 48%. low-wick = min(87, 39) = 39%.
   up-wick = 100-87 = 13%. Card printed 48 / 39 / 14. Same two numbers,
   rearranged into three lines, at three computations' cost. Zero information.
2. **Cut session-cumulative delta -> phase-relative delta.** The field that
   produced a wrong read. Delta since the current window began, never since open.

**Next, once phase definition is settled and one piece is shown working:**

3. Replace efficiency, direction-change rate, and travel with the two-window
   versions. These are good measurements pointed at the wrong window. Note
   direction changes has a second bug independent of phase blending: it's a
   monotonically growing count, so it can never report that the market *just
   started* trending — it only ratchets. It must become a rate, not a count.
4. Base detection off the ratios.
5. Levels: **POC is currently rendering `--`** — broken, and it's what entry and
   stop placement depend on. Fix before anything is layered on it. POC alone is
   also insufficient: needs VAH/VAL for the shelf edges, plus HVN/LVN — LVNs are
   targets (price travels fast through them), HVNs are what a stop sits behind.
6. Percentile-vs-history last. Correctly identified as its own build (script +
   cached table keyed on session-elapsed-bars), not a formula. Don't let it block
   the rest.

Keep `high formed X% in / low formed Y% in` as-is — the one genuinely
forward-looking field on the card, and a timestamp is legitimately session-scoped.

## Validation before building on any of it

Recompute over the NY session of **25 Jun '26** — the crash-then-base one. The
crash window should read efficiency ~0.9 and the base window ~0.15. If the two
windows don't separate those two phases on a session this visually obvious, the
phase definition is wrong and nothing downstream is worth building yet.

Also unresolved on that card: it reported `low formed 77% in`, but on the chart
the low sits around 40% across, right at the end of the impulse. Either a bug or
a session-boundary mismatch — worth checking while you're in here.
