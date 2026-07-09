/**
 * The bounded display buffer: what the chart holds, and nothing more.
 *
 * One job: keep the bars currently drawn, append the newest, and drop the
 * oldest once the buffer outgrows its cap. That is a *drawing* concern - the
 * dataset can be six million bars and a chart can show a few thousand.
 *
 * It used to own the replay cursor and prefetch bars ahead of it. Both moved to
 * the server: the cursor lives with the indicator state it advances, and bars
 * arrive inside each snapshot. What remains is a ring of candles.
 *
 * Trimming happens in `trimChunkBars` batches, not one bar at a time, because a
 * trim forces the chart to rebuild its series and doing that every bar would be
 * the exact stutter this design exists to avoid.
 */

export class BarBuffer {
  constructor(cfg) {
    this.cfg = cfg;
    this.bars = [];
    this.firstIndex = 0;   // dataset index of bars[0]
    this.total = 0;
  }

  /** Replace the buffer with the warmed-up history. */
  seed(bars, firstIndex, total) {
    this.bars = bars;
    this.firstIndex = firstIndex;
    this.total = total;
    return this.bars;
  }

  /** Dataset index of the newest bar held, or -1. */
  get cursor() {
    return this.bars.length ? this.firstIndex + this.bars.length - 1 : -1;
  }

  /**
   * Append a bar. Returns how many fell off the front (0 unless a trim fired).
   *
   * The caller uses the count to shift the chart's visible range by the same
   * amount, so a trim never moves the view.
   */
  push(bar) {
    this.bars.push(bar);
    if (this.bars.length <= this.cfg.maxBufferBars) return 0;

    const n = this.cfg.trimChunkBars;
    this.bars.splice(0, n);
    this.firstIndex += n;
    return n;
  }

  /** The oldest bar time still drawn - marks older than this can be discarded. */
  get oldestTime() {
    return this.bars.length ? this.bars[0].time : 0;
  }

  /** The newest bar time held. A snapshot at or before it is a straggler. */
  get newestTime() {
    return this.bars.length ? this.bars[this.bars.length - 1].time : 0;
  }
}
