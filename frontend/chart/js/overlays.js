/**
 * Draw what Python computed. Nothing here knows what an indicator means.
 *
 * One job: fetch the overlay specs for a bar range and render them. This module
 * understands *shapes* - a dashed vertical rule, a dot on a bar - and never a
 * session, an absorption, or a regime. When a new indicator earns a drawing, it
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
    let markers = [];
    let segments = [];
    let levels = [];
    for (const overlay of overlays) {
      if (overlay.kind === 'vlines') lines = lines.concat(overlay.lines);
      else if (overlay.kind === 'markers') markers = markers.concat(overlay.markers);
      else if (overlay.kind === 'segments') segments = segments.concat(overlay.segments);
      else if (overlay.kind === 'levels') levels = levels.concat(overlay.levels);
    }
    this.surface.setVerticalLines(lines);
    this.surface.setMarkers(markers);
    this.surface.setSegments(segments);
    this.surface.setPriceLines(levels);
  }

  clear() {
    this._seq++;
    this.surface.setVerticalLines([]);
    this.surface.setMarkers([]);
    this.surface.setSegments([]);
    this.surface.setPriceLines([]);
  }
}
