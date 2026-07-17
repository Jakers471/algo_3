# algo_metrics/ — the statistics learning papers

Self-contained HTML papers (plus PNG studies) that teach the core statistics behind
algorithmic trading, built because Jake kept meeting the same objects everywhere —
standard deviation, the normal distribution, "2-sigma" — without anyone ever explaining
what they actually are, what the axes mean, or why they matter. Every figure is computed
from this repo's real data (`data/NQ/NQ_1d.parquet`, 5,045 trading days, 2005–2025);
nothing is a textbook toy. All are wired into `commands.bat` → Analysis → Papers.

## Why these exist

Jake's opening question (July 2026): *"I keep seeing these everywhere — standard
deviation, normal distribution, 2-standard-deviation. Why do I keep seeing them, what do
they help me see and understand, and why? I'm not well versed in this area and I want to
learn. I'm a very visual person — I want images, charts, explanations. Break down the
x-axis, the y-axis, everything I need to know. What's the central theme of all of this?"*
— plus an explicit request to actually research it on the internet, not answer from
memory. The papers fold in web research (Zerodha Varsity, bollingerbands.com, QuantInsti,
Macroption, the CFA Institute sigma fact-file, Six Figure Investing, Wikipedia — sources
listed at the bottom of each paper) but every number shown is measured from our own bars.

The style rules these papers follow, learned from Jake's follow-up questions:

- **Every formula is dissected piece by piece** ("explain them in pieces then put
  together — like each function in the formula"). Each ingredient gets drawn on its own
  panel on real bars, then assembled. No step skipped, no symbol left undefined.
- **Plain words before math.** "I still don't understand what sigma is or means exactly"
  produced Figure 3a of the sigma paper: sigma drawn as a physical measuring stick in
  points, laid next to real candles, plus a one-breath definition box. Every jargon pair
  gets pinned down the same way ("wdym promised, wdym real?" → the predicted-vs-counted
  box: *predicted* = ask the curve's formula, *counted* = literally count the real days).
- **Additive edits only.** When Jake asks to add an explanation, existing prose he has
  already read stays verbatim; new material is inserted around it.
- **Honest numbers, including the ugly ones.** Where the theory breaks on real data, the
  paper measures the break instead of hiding it (33 four-sigma days where the bell curve
  budgets 0.3; Bollinger bands holding 90.4% of closes, not 95%; the back-adjustment
  caveat that mutes 2008).

## The files

| File | What it covers and why |
|------|------------------------|
| `sigma_paper.py` → `sigma_paper.html` | **The main paper: sigma as the market's ruler.** Prices vs returns (why sigma is computed on returns — and Figure 1c, built for Jake's question *"you're saying they both = 0? no average, no edge essentially? is that why I see no directional edge?"*: the returns do NOT cancel — they sum to +154%, price IS the accumulated returns, the drift is real but ~27x smaller than the daily noise). What a histogram is (a time series turned sideways). What sigma IS (the stick), then computed by hand on ten real days. Where √252 comes from, measured. The bell curve and 68-95-99.7, predicted vs counted. The fat tails where the curve lies by orders of magnitude. Volatility clustering (the ruler stretches). Then every tool as one recipe — Bollinger (with anatomy, and a click-open panel of **real walk-forward backtests, no look-ahead**: mean reversion 1.30x, breakout 0.71x, buy-and-hold 4.65x — bands describe volatility, they are not a directional edge), z-score (assembled on volume to prove portability), VaR (where 1.645 comes from + dollars on $100k), vol targeting, Sharpe (assembled from monthly bars). Central theme: sigma is a unit conversion from points into "how unusual is this?" — and the two warnings: the ruler stretches, and it lies in the tails. |
| `four_means.py` → four PNGs | **Jake's question: "what if we measured all 4 means on the data? useful?"** Yes: arithmetic = the drift (flattering), geometric = what you actually compound (the gap is the volatility drag, sigma²/2 — lever 3x and the drag grows 9x), RMS = it IS the volatility (plotted against sigma: same line), harmonic = what a fixed-dollar buyer (DCA) actually pays. Closing result: on daily gross returns the four means land in fixed order with all three gaps equal to half the daily variance (0.34 bp) — the spacing between the means IS the risk. |
| `four_means_paper.py` → `four_means_paper.html` | **The same four means, dissected.** Each mean reframed as a "flattening" that preserves one property (sum / product / reciprocals / squares), first on the textbook numbers (4, 36, 45, 50, 75) then by hand on ten real dated NQ days with full arithmetic tables, plus the vol-drag walk, the DCA units-bought figure, and the equal-gap ladder. One-breath summary box per mean and a when-to-use-which verdict. |

## Questions Jake asked that shaped these papers

1. "Why do I keep seeing standard deviation / normal distribution / 2-sigma everywhere,
   and what do they help me see?" → the whole sigma paper; central theme in section 8.
2. "The first and second graph — you're saying they both equal zero? Everything cancels,
   no average, no edge essentially? Is that why I see no directional edge?" → Figure 1c
   and its prose: the misreading named and answered (drift is real, tiny per day,
   undeniable over 20 years; direction-prediction is a separate, empirical question).
3. "Wdym promised, wdym real — makes no sense to me" → the predicted-vs-counted box and
   table in section 4.
4. "I still don't understand what sigma is or means exactly" → the one-breath box and
   Figure 3a (the stick).
5. "Explain each component in pieces then put together — each function in the formula" →
   the anatomy figures throughout (sigma by hand, √252 measured, Bollinger's two pieces,
   the z-score in four panels, VaR's 1.645 derived, Sharpe assembled).
6. "What if we measured all 4 means on the data? Useful? Let's find out" → `four_means.py`
   and the four-means paper.
7. "Show actual backtested Bollinger strategies on real NQ data, no look-ahead bias" →
   the collapsible backtest panel in section 7a.

## How to run

Everything is in the menu: `commands.bat` → Analysis → Papers. Or directly:

```
python -m scratch.algo_metrics.sigma_paper        # writes + open sigma_paper.html
python -m scratch.algo_metrics.four_means         # writes the four PNGs
python -m scratch.algo_metrics.four_means_paper   # writes four_means_paper.html
```
