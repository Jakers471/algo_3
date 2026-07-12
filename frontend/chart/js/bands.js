/**
 * A lightweight-charts primitive that shades full-height background bands.
 *
 * One job: given `{time, color}` marks, tint each bar's slot - half a bar
 * either side of its centre - from the top of the pane to the bottom. It knows
 * nothing about regimes; the backend decides which bars get which tint. Any
 * future indicator wanting background shading reuses this untouched.
 *
 * Drawn at zOrder 'bottom', beneath the candles and every other primitive:
 * shading is context, and context must never sit on top of price.
 *
 * Runs of same-coloured adjacent slots are merged into one rectangle before
 * filling, so translucent colours never double up at the seam between bars.
 * Like vertical_lines.js, all drawing is in BITMAP coordinates.
 */

export class Bands {
  constructor() {
    this._bands = [];
    this._paneView = new BandsPaneView(this);
  }

  /** Replace the marks. Cheap; triggers a repaint. */
  setBands(bands) {
    this._bands = [...(bands || [])].sort((a, b) => a.time - b.time);
    if (this._requestUpdate) this._requestUpdate();
  }

  get bands() {
    return this._bands;
  }

  // --- ISeriesPrimitive ---------------------------------------------------

  attached({ chart, requestUpdate }) {
    this._chart = chart;
    this._requestUpdate = requestUpdate;
  }

  detached() {
    this._chart = null;
    this._requestUpdate = null;
  }

  updateAllViews() {}

  paneViews() {
    return [this._paneView];
  }

  get chart() {
    return this._chart;
  }
}

class BandsPaneView {
  constructor(source) {
    this._source = source;
  }

  // Beneath everything: shading is background, and a candle must never hide
  // behind it.
  zOrder() {
    return 'bottom';
  }

  renderer() {
    return {
      draw: (target) => this._draw(target),
    };
  }

  _draw(target) {
    const chart = this._source.chart;
    const bands = this._source.bands;
    if (!chart || bands.length === 0) return;

    const timeScale = chart.timeScale();
    const spacing = timeScale.options().barSpacing;

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hr = scope.horizontalPixelRatio;
      const height = scope.bitmapSize.height;
      const half = (spacing * hr) / 2;

      ctx.save();
      // Merge contiguous same-colour slots into one rect. Adjacent bars sit
      // exactly one barSpacing apart on the logical scale (session gaps do not
      // widen it), so a gap wider than half a slot means a bar between them
      // carried no band - leave it unshaded rather than bridging it.
      let run = null;
      const flush = () => {
        if (!run) return;
        ctx.fillStyle = run.color;
        ctx.fillRect(run.x1, 0, run.x2 - run.x1, height);
        run = null;
      };
      for (const band of bands) {
        const x = timeScale.timeToCoordinate(band.time);
        if (x === null) {   // scrolled out of view
          flush();
          continue;
        }
        const cx = x * hr;
        const x1 = cx - half;
        const x2 = cx + half;
        if (run && band.color === run.color && x1 - run.x2 < half) {
          run.x2 = x2;
        } else {
          flush();
          run = { color: band.color, x1, x2 };
        }
      }
      flush();
      ctx.restore();
    });
  }
}
