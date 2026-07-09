/**
 * Build the chart surface: dark, gridless, and free to zoom.
 *
 * One job: create the chart and its price/volume series, and own the two
 * operations that touch the time scale in a way replay depends on -
 * `rebuild()` (setData without throwing away the user's zoom) and `push()`
 * (append one bar). Replay logic lives in replay/. It draws; it never computes.
 */

import { Segments } from './segments.js';
import { VerticalLines } from './vertical_lines.js';

const UP = '#26a69a';
const DOWN = '#ef5350';
const BG = '#0d1117';
const AXIS = '#1c2128';
const TEXT = '#7d8590';

/** Create the chart, candles, the delta strip and the volume overlay. */
export function createChart(container, cfg = {}) {
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

  // Signed volume, in its own strip: aggressive buying above the zero line,
  // aggressive selling below. Colours and placement come from the backend, with
  // the indicator they belong to. A bar with no order flow contributes no point,
  // so on the NT8 datasets this strip is simply empty - never a flat zero line,
  // which would claim buying and selling were balanced.
  const flow = cfg.orderflow || {};
  const delta = chart.addHistogramSeries({
    priceScaleId: 'delta',
    base: 0,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  delta.priceScale().applyOptions({
    scaleMargins: { top: flow.paneTop ?? 0.72, bottom: flow.paneBottom ?? 0.17 },
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

  // Polylines bounded in time and priced on the candle scale: the structure
  // staircase, and the level a break took out. Attached after the rules so the
  // rules stay legible over them.
  const segments = new Segments();
  candles.attachPrimitive(segments);

  return new ChartSurface(chart, candles, volume, delta, vlines, segments, flow);
}

const volumeBar = (bar) => ({
  time: bar.time,
  value: bar.volume,
  color: bar.close >= bar.open ? 'rgba(38,166,154,0.35)' : 'rgba(239,83,80,0.35)',
});

class ChartSurface {
  constructor(chart, candles, volume, delta, vlines, segments, flow) {
    this.chart = chart;
    this.candles = candles;
    this.volume = volume;
    this.delta = delta;
    this.vlines = vlines;
    this.segments = segments;
    this.flow = flow;
    this._priceLines = [];
  }

  /** A delta bar, or null when this dataset has no order flow (never a zero). */
  deltaBar(bar) {
    if (!this.flow.draw || bar.delta === null || bar.delta === undefined) return null;
    return {
      time: bar.time,
      value: bar.delta,
      color: bar.delta >= 0 ? this.flow.upColor : this.flow.downColor,
    };
  }

  /** Drop dashed rules with labels. `lines` are {time, label, color, labelColor}. */
  setVerticalLines(lines) {
    this.vlines.setLines(lines);
  }

  /** Stroke polylines. `segments` are {points: [{time, price}], color, width}. */
  setSegments(segments) {
    this.segments.setSegments(segments);
  }

  /**
   * Horizontal price lines across the pane, labelled on the axis.
   *
   * `levels` are {price, color, width, title, dashed}. Replaced wholesale: a
   * level is a reading of the present, so there is no such thing as an old one
   * worth keeping. lightweight-charts has no setter, only create/remove, so we
   * hold the handles ourselves.
   */
  setPriceLines(levels) {
    for (const line of this._priceLines) this.candles.removePriceLine(line);
    this._priceLines = (levels || []).map((level) => this.candles.createPriceLine({
      price: level.price,
      color: level.color,
      lineWidth: level.width || 1,
      lineStyle: level.dashed ? LightweightCharts.LineStyle.Dashed
                              : LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: level.title || '',
    }));
  }

  /**
   * Dots on bars. `markers` are {time, position, color, shape, text}.
   *
   * lightweight-charts requires them in ascending time order and silently
   * misplaces them otherwise, so sort rather than trust the caller.
   */
  setMarkers(markers) {
    this.candles.setMarkers([...markers].sort((a, b) => a.time - b.time));
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
    this.delta.setData(bars.map((b) => this.deltaBar(b)).filter(Boolean));

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
    const point = this.deltaBar(bar);
    if (point) this.delta.update(point);
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
