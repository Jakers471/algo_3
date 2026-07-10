/**
 * Boot the chart and connect the pieces.
 *
 * One job: construct surface, browser, engine and controls, and route events
 * between them. All the weight lives in those modules - this file only decides
 * who talks to whom.
 *
 * There are deliberately no indicators here. Indicators are computed in Python
 * and arrive as drawing instructions; the chart never calculates one. A second
 * implementation in JavaScript would drift from the backtest, and the day it
 * drifts is the day a chart contradicts a backtest. See BUILD_PLAN.md.
 *
 * Two modes, two sources. Browse pulls bars and overlays for whatever window is
 * on screen. Replay subscribes to a server-side session that owns the cursor and
 * the live indicator state, and draws each snapshot as it is published.
 */

import { getConfig, getDatasets, locate } from './api.js';
import { Browser } from './browse.js';
import { createChart } from './chart.js';
import { Layers } from './layers.js';
import { LayersPanel } from './layers_panel.js';
import { OverlayLayer } from './overlays.js';
import { Controls } from './replay/controls.js';
import { ReplayEngine } from './replay/engine.js';

async function boot() {
  const [cfg, datasets] = await Promise.all([getConfig(), getDatasets()]);
  if (Object.keys(datasets).length === 0) {
    const hint = document.getElementById('hint');
    hint.textContent = 'No packed data. Run: python -m src.cli.chart --repack';
    hint.classList.add('visible');
    return;
  }

  const surface = createChart(document.getElementById('chart'), cfg);
  const layers = new Layers(cfg.layers || []);
  LayersPanel(document.getElementById('layers'), layers);
  const overlays = new OverlayLayer(surface, layers);
  const browser = new Browser(surface, overlays, cfg);
  const engine = new ReplayEngine(cfg, surface, layers);

  engine.on('bar', ({ bar, seeded }) => {
    if (bar) {
      controls.showBar(bar);
      controls.setDate(bar.time);
    }
    if (!seeded) controls.showProgress(engine.cursor, engine.total);
  });

  const controls = new Controls({
    engine,
    browser,
    surface,
    datasets,
    profileSymbols: cfg.profileSymbols || [],
    profileBaseTimeframe: cfg.profileBaseTimeframe,

    /** Cut back to a point in time; the server seeds and starts publishing. */
    async onStart(epochSeconds) {
      const { index } = await locate(controls.symbol, controls.timeframe, epochSeconds);
      controls.setMode('replay');
      // Browse and replay share one surface. Hand it over before replay draws,
      // or a scroll-triggered backfill will rebuild the series out from under it.
      browser.suspend();
      await engine.start(controls.symbol, controls.timeframe, index, controls.profile);
      controls.showProgress(engine.cursor, engine.total);
    },

    /**
     * Switch which volume-profile range is drawn.
     *
     * The indicator's state IS the range it has accumulated, so this cannot be
     * a setting toggled mid-flight: replay re-seeds at the bar it had reached
     * (the same machinery a retired session uses), and browse simply refetches.
     */
    async onProfileChange(mode) {
      overlays.profile = mode;
      if (controls.mode === 'replay' && engine.symbol) {
        await engine.start(engine.symbol, engine.timeframe, engine.cursor + 1, mode);
      } else {
        overlays.refresh(browser.symbol, browser.timeframe, browser.firstIndex, browser.bars);
      }
    },

    /** Leave replay: retire the session, go back to the live tail of the data. */
    async onExit() {
      await engine.stop();
      await browser.load(controls.symbol, controls.timeframe);
      const last = browser.bars[browser.bars.length - 1];
      if (last) { controls.showBar(last); controls.setDate(last.time); }
      controls.showProgress(browser.total, browser.total);
    },
  });

  await controls.onExit();
}

boot().catch((err) => {
  console.error(err);
  const hint = document.getElementById('hint');
  hint.textContent = `Failed to start: ${err.message}`;
  hint.classList.add('visible');
});
