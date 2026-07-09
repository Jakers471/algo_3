/**
 * Boot the chart and connect the pieces.
 *
 * One job: construct surface, indicators, browser, engine and controls, and
 * route events between them. All the weight lives in those modules - this file
 * only decides who talks to whom. Add an indicator by importing it and calling
 * `indicators.add(...)` below; nothing else changes.
 */

import { getConfig, getDatasets, locate } from './api.js';
import { Browser } from './browse.js';
import { createChart } from './chart.js';
import { IndicatorRegistry } from './indicators/registry.js';
import { sma } from './indicators/sma.js';
import { Controls } from './replay/controls.js';
import { ReplayEngine } from './replay/engine.js';

async function boot() {
  const [cfg, datasets] = await Promise.all([getConfig(), getDatasets()]);
  if (Object.keys(datasets).length === 0) {
    document.getElementById('hint').textContent =
      'No packed data. Run: python -m src.cli.chart --repack';
    document.getElementById('hint').classList.add('visible');
    return;
  }

  const surface = createChart(document.getElementById('chart'));

  const indicators = new IndicatorRegistry(surface.chart);
  indicators.add(sma(20, '#58a6ff'));
  indicators.add(sma(50, '#d29922'));

  const browser = new Browser(surface, indicators, cfg);
  const engine = new ReplayEngine(cfg);

  // Replay redraws through exactly three paths, cheapest first.
  engine.on('bar', ({ bar, trimmed, bars, seeded }) => {
    if (seeded) {
      // New cut point: everything is new.
      surface.rebuild(bars);
      indicators.rebuild(bars);
      surface.fit();
    } else if (trimmed) {
      // The buffer shed its oldest chunk; rebuild, holding the user's zoom.
      surface.rebuild(bars, trimmed);
      indicators.rebuild(bars);
    } else {
      // The common case: one bar appended, no redraw.
      surface.push(bar);
      indicators.push(bars);
    }

    if (bar) {
      controls.showBar(bar);
      controls.setDate(bar.time);
    }
    controls.showProgress(engine.window.cursor, engine.window.total);
  });

  const controls = new Controls({
    engine,
    browser,
    surface,
    indicators,
    datasets,

    /** Cut back to a point in time and hand the bars to replay. */
    async onStart(epochSeconds) {
      const { index } = await locate(controls.symbol, controls.timeframe, epochSeconds);
      controls.setMode('replay');
      await engine.start(controls.symbol, controls.timeframe, index);
    },

    /** Leave replay: back to the live tail of the data. */
    async onExit() {
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
