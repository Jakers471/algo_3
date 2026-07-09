/**
 * Browse mode: the ordinary chart you look at when replay is off.
 *
 * One job: show the most recent bars, and lazily pull older ones in as the user
 * scrolls back - so opening a 6M-bar 1m dataset costs one small fetch, not 150MB.
 *
 * The same bounded-window idea as replay, pointed backwards: we hold a run of
 * bars and extend its front on demand, never the whole dataset.
 */

import { getBars } from './api.js';

// Start backfilling once the view comes within this many bars of the loaded edge.
const BACKFILL_TRIGGER_BARS = 100;

export class Browser {
  constructor(surface, cfg) {
    this.surface = surface;
    this.cfg = cfg;

    this.bars = [];
    this.firstIndex = 0;   // dataset index of bars[0]
    this.total = 0;
    this._loading = false;

    this.surface.onVisibleRangeChange((range) => this._maybeBackfill(range));
  }

  /** Load the newest `historyBars` bars of a symbol/timeframe and frame them. */
  async load(symbol, timeframe) {
    this.symbol = symbol;
    this.timeframe = timeframe;

    // start=0,count=0 is the cheap way to ask "how many bars are there?" - the
    // server answers with an empty body and the true total in X-Total.
    const probe = await getBars(symbol, timeframe, 0, 0);
    const start = Math.max(0, probe.total - this.cfg.historyBars);

    const { bars, start: got, total } = await getBars(
      symbol, timeframe, start, this.cfg.historyBars,
    );
    this.bars = bars;
    this.firstIndex = got;
    this.total = total;

    this.surface.rebuild(this.bars);
    this.surface.fit();
    return this.bars;
  }

  /** Prepend the previous chunk when the user scrolls near the loaded edge. */
  async _maybeBackfill(range) {
    if (!range || this._loading || this.firstIndex === 0 || !this.symbol) return;
    if (range.from > BACKFILL_TRIGGER_BARS) return;

    this._loading = true;
    try {
      const count = Math.min(this.cfg.prefetchBars, this.firstIndex);
      const from = this.firstIndex - count;
      const { bars } = await getBars(this.symbol, this.timeframe, from, count);
      if (bars.length === 0) return;

      this.bars = bars.concat(this.bars);
      this.firstIndex = from;

      // Bars were added to the front, so every existing bar moved RIGHT by
      // bars.length: a negative shift-left.
      this.surface.rebuild(this.bars, -bars.length);
    } catch (err) {
      console.error('backfill failed', err);
    } finally {
      this._loading = false;
    }
  }
}
