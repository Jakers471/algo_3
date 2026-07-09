/**
 * The sliding bar window: what replay holds in memory, and nothing more.
 *
 * One job: own a bounded buffer of revealed bars and a prefetched run of
 * un-revealed ones, so stepping forward is O(1) and never waits on the network.
 *
 * The shape of the problem: the dataset is up to ~6M bars, but a chart can only
 * ever show a few thousand. So we keep `historyBars` behind the cursor - enough
 * to zoom out into real context - and drop the rest. Trimming happens in
 * `trimChunkBars` batches rather than one bar at a time, because a trim forces
 * the chart to rebuild its series, and doing that every bar would be the exact
 * stutter this design exists to avoid.
 *
 * Bars ahead of the cursor are fetched in `prefetchBars` runs whenever fewer
 * than `prefetchThresholdBars` remain, so the fetch overlaps playback instead
 * of blocking it.
 *
 * Knows nothing about charts, timers, or the DOM - it is a data structure.
 */

import { getBars } from '../api.js';

export class BarWindow {
  /**
   * @param {string} symbol
   * @param {string} timeframe
   * @param {object} cfg  the server's replay dials (see /api/config)
   */
  constructor(symbol, timeframe, cfg) {
    this.symbol = symbol;
    this.timeframe = timeframe;
    this.cfg = cfg;

    /** Revealed bars, oldest first. This is what the chart shows. */
    this.bars = [];
    /** Fetched but not yet revealed, contiguous from dataset index `next`. */
    this.ahead = [];
    /** Dataset index of the next bar to reveal. */
    this.next = 0;
    /** Total bars in the dataset, per the server. */
    this.total = 0;

    this._fetching = null;
  }

  /** True once the cursor has consumed the whole dataset. */
  get atEnd() {
    return this.total > 0 && this.next >= this.total && this.ahead.length === 0;
  }

  /** Dataset index of the newest revealed bar, or -1. */
  get cursor() {
    return this.next - 1;
  }

  /**
   * Start replay at `startIndex`: reveal the history behind it, nothing ahead.
   *
   * This is the "cut back in time" operation - everything at or after
   * `startIndex` is unseen, and the chart shows only what a trader standing at
   * that bar could have known.
   */
  async seed(startIndex) {
    const { historyBars } = this.cfg;
    const from = Math.max(0, startIndex - historyBars);
    const { bars, start, total } = await getBars(
      this.symbol, this.timeframe, from, startIndex - from,
    );

    this.total = total;
    this.bars = bars;
    this.ahead = [];
    this.next = start + bars.length;
    await this._fill();
    return this.bars;
  }

  /**
   * Reveal the next bar.
   *
   * Returns `{ bar, trimmed }` - `trimmed` is how many bars fell off the front,
   * which is non-zero only on a trim batch. The caller uses it to rebuild the
   * chart series and shift the visible range to compensate. Returns null at the
   * end of the data.
   */
  async step() {
    if (this.ahead.length === 0) {
      await this._fill();
      if (this.ahead.length === 0) return null;
    }

    const bar = this.ahead.shift();
    this.bars.push(bar);
    this.next += 1;

    // Refill in the background; do not await, so the step lands this frame.
    if (this.ahead.length < this.cfg.prefetchThresholdBars) {
      this._fill().catch((err) => console.error('prefetch failed', err));
    }

    return { bar, trimmed: this._trim() };
  }

  /** Drop the oldest chunk once the buffer outgrows its cap. */
  _trim() {
    if (this.bars.length <= this.cfg.maxBufferBars) return 0;
    const n = this.cfg.trimChunkBars;
    this.bars.splice(0, n);
    return n;
  }

  /**
   * Pull the next run of bars into `ahead`.
   *
   * Guarded by a single in-flight promise: playback can call this from several
   * steps before the first resolves, and issuing overlapping requests for the
   * same range would both waste bandwidth and corrupt `ahead`'s ordering.
   */
  _fill() {
    if (this._fetching) return this._fetching;

    const from = this.next + this.ahead.length;
    if (this.total && from >= this.total) return Promise.resolve();

    this._fetching = getBars(this.symbol, this.timeframe, from, this.cfg.prefetchBars)
      .then(({ bars, total }) => {
        this.total = total;
        this.ahead.push(...bars);
      })
      .finally(() => { this._fetching = null; });

    return this._fetching;
  }
}
