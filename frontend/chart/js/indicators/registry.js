/**
 * The indicator seam: register a calculation, get it drawn - in replay too.
 *
 * One job: hold the registered indicators, give each a series on the chart, and
 * keep them in step with the bar window through both paths the chart changes:
 * a full rebuild (seed / buffer trim) and a single appended bar (each replay step).
 *
 * An indicator is a plain object. Nothing here knows what an SMA is:
 *
 *   {
 *     id:      'sma20',                     // unique
 *     label:   'SMA 20',                    // shown in the toggle list
 *     create:  (chart) => series,           // add your series to the chart
 *     compute: (bars) => points[],          // full recompute, for setData
 *     last:    (bars) => point | null,      // just the newest point, for update
 *   }
 *
 * `last` exists for speed: on every replay step only the newest point changed,
 * and recomputing the whole series 5,000 bars deep at 4x would be wasted work.
 * An indicator that cannot compute incrementally may set `last: null` and the
 * registry falls back to a full recompute for it.
 *
 * Because indicators recompute off `window.bars` - the same bounded buffer the
 * chart draws - they see exactly the bars a trader at the cursor could see. No
 * indicator can peek at the future during replay.
 */

export class IndicatorRegistry {
  constructor(chart) {
    this.chart = chart;
    this.items = new Map();
  }

  /** Register and draw an indicator. Returns it, so callers can toggle later. */
  add(indicator) {
    if (this.items.has(indicator.id)) throw new Error(`duplicate indicator '${indicator.id}'`);
    const series = indicator.create(this.chart);
    this.items.set(indicator.id, { indicator, series, visible: true });
    return indicator;
  }

  /** Show or hide one indicator without discarding its series or its data. */
  setVisible(id, visible) {
    const entry = this.items.get(id);
    if (!entry) return;
    entry.visible = visible;
    entry.series.applyOptions({ visible });
  }

  /** Full recompute for every indicator. Call on seed, timeframe change, or trim. */
  rebuild(bars) {
    for (const { indicator, series } of this.items.values()) {
      series.setData(indicator.compute(bars));
    }
  }

  /** One new bar landed: extend each indicator by its newest point. */
  push(bars) {
    for (const { indicator, series } of this.items.values()) {
      if (typeof indicator.last === 'function') {
        const point = indicator.last(bars);
        if (point) series.update(point);
      } else {
        series.setData(indicator.compute(bars));
      }
    }
  }

  /** The registered indicators, for building a toggle UI. */
  list() {
    return [...this.items.values()].map(({ indicator, visible }) => ({
      id: indicator.id, label: indicator.label, visible,
    }));
  }
}
