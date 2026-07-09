/**
 * Draw what Python computed. Nothing here knows what an indicator means.
 *
 * One job: fetch the overlay specs for a bar range and render them. This module
 * understands *shapes* - today a dashed vertical rule with a label - and never a
 * session, a regime, or a value area. When a new indicator earns a drawing, it
 * reuses a shape that already exists here, and this file does not change.
 *
 * That asymmetry is deliberate. Indicator logic lives in Python, once. If it
 * also lived here it would drift, and a drifting chart contradicts a backtest
 * with no way to tell which one lied.
 */

import { getOverlays } from './api.js';

export class OverlayLayer {
  constructor(surface) {
    this.surface = surface;
    this._seq = 0;   // guards against a slow response overwriting a newer one
  }

  /**
   * Fetch and draw the overlays for the bars currently on screen.
   *
   * `startIndex` is the dataset index of `bars[0]`, so the server recomputes
   * indicators over exactly the bars we have revealed - never a bar beyond them.
   */
  async refresh(symbol, timeframe, startIndex, bars) {
    if (!bars.length) return;
    const seq = ++this._seq;
    try {
      const { overlays } = await getOverlays(symbol, timeframe, startIndex, bars.length);
      if (seq !== this._seq) return;   // a newer refresh already landed
      this.draw(overlays);
    } catch (err) {
      console.error('overlay refresh failed', err);
    }
  }

  /** Render each overlay by its shape. Unknown shapes are ignored, not fatal. */
  draw(overlays) {
    let lines = [];
    for (const overlay of overlays) {
      if (overlay.kind === 'vlines') lines = lines.concat(overlay.lines);
    }
    this.surface.setVerticalLines(lines);
  }

  clear() {
    this._seq++;
    this.surface.setVerticalLines([]);
  }
}
