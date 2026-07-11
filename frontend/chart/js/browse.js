/**
 * Browse mode: the ordinary chart you look at when replay is off.
 *
 * One job: show the most recent bars, and lazily pull older ones in as the user
 * scrolls back - so opening a 6M-bar 1m dataset costs one small fetch, not 150MB.
 *
 * The same bounded-window idea as replay, pointed backwards: we hold a run of
 * bars and extend its front on demand, never the whole dataset.
 */

import { getBars, locate } from './api.js';

// Start backfilling once the view comes within this many bars of the loaded edge.
const BACKFILL_TRIGGER_BARS = 100;

export class Browser {
  constructor(surface, overlays, cfg) {
    this.surface = surface;
    this.overlays = overlays;
    this.cfg = cfg;

    this.bars = [];
    this.firstIndex = 0;   // dataset index of bars[0]
    this.total = 0;
    this._loading = false;
    this.active = false;

    // The subscription lives for the life of the chart, but the handler must
    // not: browse and replay share one surface, and zoom stays live during a
    // replay. A backfill fired then would rebuild the series with the TAIL of
    // the dataset - thousands of bars ahead of the replay cursor - and the next
    // snapshot would be handed to a chart whose newest bar is in its future.
    this.surface.onVisibleRangeChange((range) => this._maybeBackfill(range));
  }

  /** Stop touching the surface. Replay owns it now. */
  suspend() {
    this.active = false;
  }

  /** Load the newest `historyBars` bars of a symbol/timeframe and frame them. */
  async load(symbol, timeframe) {
    this.symbol = symbol;
    this.timeframe = timeframe;
    this.active = true;

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
    this.overlays.refresh(symbol, timeframe, this.firstIndex, this.bars);
    return this.bars;
  }

  /**
   * Load a symbol/timeframe centred on a TIME window, then frame that window.
   *
   * This is what keeps a timeframe switch in place. `load` always grabs the tail
   * and fits it, which throws you to the front; here the caller passes the window
   * it was looking at, we pull the new timeframe's bars around that time, and set
   * the visible range back to the same window - so 5m -> 1m at some moment three
   * weeks back stays at that moment, at that zoom, instead of jumping to now.
   */
  async loadAround(symbol, timeframe, timeRange) {
    this.symbol = symbol;
    this.timeframe = timeframe;
    this.active = true;

    const probe = await getBars(symbol, timeframe, 0, 0);
    const total = probe.total;
    if (!total) return this.load(symbol, timeframe);

    // Where the window's edges fall in the NEW timeframe's index space.
    const [a, z] = await Promise.all([
      locate(symbol, timeframe, timeRange.from),
      locate(symbol, timeframe, timeRange.to),
    ]);
    const span = Math.max(1, z.index - a.index);

    // Load just enough to cover the window plus margin on both sides, capped at
    // historyBars so a zoomed-out view on a fine timeframe cannot ask for millions.
    const count = Math.min(this.cfg.historyBars, span + 2 * BACKFILL_TRIGGER_BARS);
    let start = Math.max(0, a.index - Math.floor((count - span) / 2));
    start = Math.min(start, Math.max(0, total - count));

    const { bars, start: got, total: t } = await getBars(symbol, timeframe, start, count);
    this.bars = bars;
    this.firstIndex = got;
    this.total = t;

    this.surface.rebuild(this.bars);              // no fit - we set the range ourselves
    this.surface.setVisibleTimeRange(timeRange);
    this.overlays.refresh(symbol, timeframe, this.firstIndex, this.bars);
    return this.bars;
  }

  /** Prepend the previous chunk when the user scrolls near the loaded edge. */
  async _maybeBackfill(range) {
    if (!this.active) return;   // replay owns the surface
    if (!range || this._loading || this.firstIndex === 0 || !this.symbol) return;
    if (range.from > BACKFILL_TRIGGER_BARS) return;

    this._loading = true;
    try {
      const count = Math.min(this.cfg.prefetchBars, this.firstIndex);
      const from = this.firstIndex - count;
      const { bars } = await getBars(this.symbol, this.timeframe, from, count);
      // The fetch is slow enough for replay to have started underneath it.
      if (bars.length === 0 || !this.active) return;

      this.bars = bars.concat(this.bars);
      this.firstIndex = from;

      // Bars were added to the front, so every existing bar moved RIGHT by
      // bars.length: a negative shift-left.
      this.surface.rebuild(this.bars, -bars.length);
      this.overlays.refresh(this.symbol, this.timeframe, this.firstIndex, this.bars);
    } catch (err) {
      console.error('backfill failed', err);
    } finally {
      this._loading = false;
    }
  }
}
