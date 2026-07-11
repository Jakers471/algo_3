/**
 * A lightweight-charts primitive that draws dashed vertical rules with labels.
 *
 * One job: given `{time, label, color, labelColor}` marks, draw a dashed line
 * down the pane at each one and print its label beside it. It knows nothing
 * about sessions - the backend decides where the lines go and what they say.
 * Any future indicator wanting a vertical mark reuses this untouched.
 *
 * Lightweight-charts has no vertical-line series, so this hooks the v4 primitive
 * API: `series.attachPrimitive()` gives us a pane view whose renderer draws onto
 * the chart's own canvas, in sync with every pan and zoom.
 *
 * All drawing happens in BITMAP coordinates. The canvas is sized in device
 * pixels, so a CSS-pixel x from `timeToCoordinate` must be scaled by the pixel
 * ratio, otherwise the lines drift from the candles on any non-1x display.
 */

const LABEL_FONT_PX = 11;
const LABEL_PAD_X = 5;
const LABEL_TOP_Y = 6;
const DASH = [4, 4];

export class VerticalLines {
  constructor() {
    this._lines = [];
    this._paneView = new VerticalLinesPaneView(this);
  }

  /** Replace the marks. Cheap; triggers a repaint. */
  setLines(lines) {
    this._lines = lines || [];
    if (this._requestUpdate) this._requestUpdate();
  }

  get lines() {
    return this._lines;
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

class VerticalLinesPaneView {
  constructor(source) {
    this._source = source;
  }

  // Above the candles: these are structure, and a candle must not hide them.
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
    const lines = this._source.lines;
    if (!chart || lines.length === 0) return;

    const timeScale = chart.timeScale();

    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { horizontalPixelRatio: hr, verticalPixelRatio: vr } = scope;
      const height = scope.bitmapSize.height;

      ctx.save();
      for (const line of lines) {
        const x = timeScale.timeToCoordinate(line.time);
        if (x === null) continue;   // scrolled out of view

        // +0.5 lands the stroke on a pixel centre, so a 1px line stays crisp.
        const px = Math.round(x * hr) + 0.5;

        ctx.setLineDash(DASH.map((d) => d * vr));
        ctx.strokeStyle = line.color;
        ctx.lineWidth = Math.max(1, Math.floor(hr));
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, height);
        ctx.stroke();

        if (line.label) {
          ctx.setLineDash([]);
          ctx.font = `${LABEL_FONT_PX * vr}px 'JetBrains Mono', Consolas, monospace`;
          ctx.textBaseline = 'top';
          ctx.fillStyle = line.labelColor || line.color;
          // Close labels ride lower (labelY) so they clear the open label of the
          // session they abut on the back-to-back boundaries.
          const labelY = line.labelY ?? LABEL_TOP_Y;
          ctx.fillText(line.label, px + LABEL_PAD_X * hr, labelY * vr);
        }
      }
      ctx.restore();
    });
  }
}
