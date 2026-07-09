/**
 * A lightweight-charts primitive that strokes polylines in (time, price) space.
 *
 * One job: given `{points: [{time, price}, ...], color, width}` segments, stroke
 * each polyline onto the chart's canvas. It knows nothing about swings, legs, or
 * breaks of structure - the backend decides where the corners go and what colour
 * they are. Any future indicator wanting a bounded line reuses this untouched.
 *
 * Why a primitive and not a line series. A series spans the whole dataset and
 * carries one colour; these lines start and stop at particular bars and each
 * carries its own. Attaching to the price series gives us `priceToCoordinate`,
 * so a corner lands on the price it names however the user has zoomed.
 *
 * All drawing happens in BITMAP coordinates, like vertical_lines.js: the canvas
 * is sized in device pixels, so a CSS-pixel coordinate must be scaled by the
 * pixel ratio or the lines drift off the candles on any non-1x display.
 *
 * A point whose time lies outside the loaded bars has no coordinate. Rather than
 * guess where it belongs, the whole polyline is skipped - a half-drawn structure
 * is worse than none, because it would draw a level that starts nowhere.
 */

export class Segments {
  constructor() {
    this._segments = [];
    this._paneView = new SegmentsPaneView(this);
  }

  /** Replace the segments. Cheap; triggers a repaint. */
  setSegments(segments) {
    this._segments = segments || [];
    if (this._requestUpdate) this._requestUpdate();
  }

  get segments() {
    return this._segments;
  }

  // --- ISeriesPrimitive ---------------------------------------------------

  attached({ chart, series, requestUpdate }) {
    this._chart = chart;
    this._series = series;
    this._requestUpdate = requestUpdate;
  }

  detached() {
    this._chart = null;
    this._series = null;
    this._requestUpdate = null;
  }

  updateAllViews() {}

  paneViews() {
    return [this._paneView];
  }

  get chart() { return this._chart; }
  get series() { return this._series; }
}

class SegmentsPaneView {
  constructor(source) {
    this._source = source;
  }

  // Under the vertical rules but over the candles: structure the candles sit in.
  zOrder() {
    return 'top';
  }

  renderer() {
    return {
      draw: (target) => this._draw(target),
    };
  }

  _draw(target) {
    const chart = this._source.chart;
    const series = this._source.series;
    const segments = this._source.segments;
    if (!chart || !series || segments.length === 0) return;

    const timeScale = chart.timeScale();

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { horizontalPixelRatio: hr, verticalPixelRatio: vr } = scope;

      ctx.save();
      ctx.lineJoin = 'miter';
      ctx.setLineDash([]);

      for (const segment of segments) {
        const pts = [];
        let missing = false;
        for (const point of segment.points) {
          const x = timeScale.timeToCoordinate(point.time);
          const y = series.priceToCoordinate(point.price);
          if (x === null || y === null) { missing = true; break; }
          // `dx` shifts a point sideways from the bar it names, in CSS pixels.
          // A volume-profile bin is a length on screen, not a span of market
          // time; anchoring its far end to an interpolated timestamp would give
          // a coordinate of null, because no bar occupies that moment.
          pts.push([(x + (point.dx || 0)) * hr, y * vr]);
        }
        // A corner we cannot place is a line we must not draw.
        if (missing || pts.length < 2) continue;

        ctx.strokeStyle = segment.color;
        ctx.lineWidth = Math.max(1, Math.round((segment.width || 1) * hr));
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
        ctx.stroke();
      }
      ctx.restore();
    });
  }
}
