/**
 * Build the chart surface: dark, gridless, and free to zoom.
 *
 * One job: create the chart and its price/volume series, and own the two
 * operations that touch the time scale in a way replay depends on -
 * `rebuild()` (setData without throwing away the user's zoom) and `push()`
 * (append one bar). Replay logic lives in replay/. It draws; it never computes.
 */

import { VerticalLines } from './vertical_lines.js';

const UP = '#26a69a';
const DOWN = '#ef5350';
const BG = '#0d1117';
const AXIS = '#1c2128';
const TEXT = '#7d8590';

/** Create the chart, candles, and the volume overlay. */
export function createChart(container) {
  const chart = LightweightCharts.createChart(container, {
    layout: {
      background: { type: 'solid', color: BG },
      textColor: TEXT,
      fontSize: 11,
      fontFamily: "'JetBrains Mono', 'Consolas', monospace",
    },
    // No grid, as asked - the candles carry the structure.
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    rightPriceScale: {
      borderColor: AXIS,
      scaleMargins: { top: 0.08, bottom: 0.25 },
    },
    timeScale: {
      borderColor: AXIS,
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 6,
      // Only shifts the view when the user is already parked at the right
      // edge, so a zoomed-out or scrolled-back view is never yanked forward.
      shiftVisibleRangeOnNewBar: true,
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: { color: '#3d444d', width: 1, style: 2, labelBackgroundColor: '#30363d' },
      horzLine: { color: '#3d444d', width: 1, style: 2, labelBackgroundColor: '#30363d' },
    },
    // Zoom and pan stay live at all times, replay included.
    handleScroll: true,
    handleScale: true,
    autoSize: true,
  });

  const candles = chart.addCandlestickSeries({
    upColor: UP,
    downColor: DOWN,
    wickUpColor: UP,
    wickDownColor: DOWN,
    borderVisible: false,
    priceLineVisible: false,
    lastValueVisible: true,
  });

  const volume = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: '',
    priceLineVisible: false,
    lastValueVisible: false,
  });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

  // Dashed rules (session opens today) drawn onto the chart's own canvas, so
  // they track every pan and zoom exactly. No vertical-line series exists.
  const vlines = new VerticalLines();
  candles.attachPrimitive(vlines);

  return new ChartSurface(chart, candles, volume, vlines);
}

const volumeBar = (bar) => ({
  time: bar.time,
  value: bar.volume,
  color: bar.close >= bar.open ? 'rgba(38,166,154,0.35)' : 'rgba(239,83,80,0.35)',
});

class ChartSurface {
  constructor(chart, candles, volume, vlines) {
    this.chart = chart;
    this.candles = candles;
    this.volume = volume;
    this.vlines = vlines;
  }

  /** Drop dashed rules with labels. `lines` are {time, label, color, labelColor}. */
  setVerticalLines(lines) {
    this.vlines.setLines(lines);
  }

  /**
   * Replace all bars, preserving the user's zoom.
   *
   * setData renumbers logical indices from zero, so any bar added to or removed
   * from the FRONT of the array silently slides the view. `shiftLeft` is how far
   * each retained bar moved: positive when bars were trimmed off the head (a
   * replay buffer trim), negative when older bars were prepended (scrolling back
   * in browse mode). We move the visible range by the same amount, so the user's
   * zoom and position survive untouched. Without this every trim would jump the
   * chart - which is exactly what makes replay feel broken.
   */
  rebuild(bars, shiftLeft = 0) {
    const ts = this.chart.timeScale();
    const range = shiftLeft ? ts.getVisibleLogicalRange() : null;

    this.candles.setData(bars);
    this.volume.setData(bars.map(volumeBar));

    if (range) {
      ts.setVisibleLogicalRange({
        from: range.from - shiftLeft,
        to: range.to - shiftLeft,
      });
    }
  }

  /** Append (or amend) the newest bar. Cheap - no full redraw. */
  push(bar) {
    this.candles.update(bar);
    this.volume.update(volumeBar(bar));
  }

  /** Frame everything currently loaded. Only ever called on an explicit action. */
  fit() {
    this.chart.timeScale().fitContent();
  }

  onClick(handler) {
    this.chart.subscribeClick(handler);
  }

  onCrosshairMove(handler) {
    this.chart.subscribeCrosshairMove(handler);
  }

  onVisibleRangeChange(handler) {
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
  }
}
