/**
 * Wire the toolbar to the engine.
 *
 * One job: DOM in, calls out. Every button here delegates to ReplayEngine or
 * Browser - no replay logic, no chart calls, no fetching. The frontend's thin door.
 *
 * Note the transport buttons do not set their own state. Play, pause and speed
 * are requests; the button repaints when the SERVER says the session changed.
 * A button that lied about the state would be a second source of truth, and the
 * TUI watching the same session would disagree with it.
 */

import { fmtPrice, fmtTime, fmtVol, fromInputValue, toInputValue } from '../format.js';

const $ = (id) => document.getElementById(id);

export class Controls {
  /**
   * @param {object} deps { engine, browser, surface, datasets, onStart, onExit }
   */
  constructor(deps) {
    Object.assign(this, deps);
    this.picking = false;

    this._buildSelectors();
    this._wireTransport();
    this._wireNavigation();
    this._wireReadout();

    this.engine.on('state', (s) => this._renderState(s));
    this.setMode('browse');
  }

  // --- symbol / timeframe ---------------------------------------------------

  _buildSelectors() {
    const symbols = Object.keys(this.datasets);
    $('symbol').innerHTML = symbols.map((s) => `<option>${s}</option>`).join('');
    $('symbol').value = symbols.includes('NQ') ? 'NQ' : symbols[0];

    const fill = () => {
      const tfs = Object.keys(this.datasets[$('symbol').value]);
      $('timeframe').innerHTML = tfs.map((t) => `<option>${t}</option>`).join('');
      $('timeframe').value = tfs.includes('5m') ? '5m' : tfs[0];
    };
    fill();

    $('symbol').addEventListener('change', () => { fill(); this._reload(); });
    $('timeframe').addEventListener('change', () => this._reload());
  }

  get symbol() { return $('symbol').value; }
  get timeframe() { return $('timeframe').value; }

  _reload() {
    this.engine.pause();
    this.setMode('browse');
    this.onExit();
  }

  // --- transport ------------------------------------------------------------

  _wireTransport() {
    $('play').addEventListener('click', () => this.engine.toggle());
    $('step').addEventListener('click', () => this.engine.step());

    for (const speed of [1, 2, 4]) {
      $(`speed-${speed}`).addEventListener('click', () => {
        this.engine.setSpeed(speed);
        this._renderSpeed(speed);   // the server echoes this back; show it now
      });
    }

    // Space plays/pauses; arrow steps. Ignored while typing in the date box.
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || this.mode !== 'replay') return;
      if (e.code === 'Space') { e.preventDefault(); this.engine.toggle(); }
      if (e.code === 'ArrowRight') { e.preventDefault(); this.engine.step(); }
    });
  }

  // --- entering replay ------------------------------------------------------

  _wireNavigation() {
    $('replay').addEventListener('click', () => {
      if (this.mode === 'replay') { this._reload(); return; }
      this._setPicking(!this.picking);
    });

    $('jump').addEventListener('click', () => {
      const value = $('datetime').value;
      if (!value) return;
      this.onStart(fromInputValue(value));
    });

    // Click-to-cut: the chart click hands back the bar's time, which the server
    // turns into a dataset index. Replay starts there.
    this.surface.onClick((param) => {
      if (!this.picking || !param.time) return;
      this._setPicking(false);
      this.onStart(param.time);
    });

    $('fit').addEventListener('click', () => this.surface.fit());
  }

  _setPicking(on) {
    this.picking = on;
    $('replay').classList.toggle('armed', on);
    $('hint').classList.toggle('visible', on);
    document.body.classList.toggle('picking', on);
  }

  // --- readout --------------------------------------------------------------

  _wireReadout() {
    // Hovering shows the hovered bar; leaving the chart restores the newest one.
    this.surface.onCrosshairMove((param) => {
      const ohlc = param.seriesData ? param.seriesData.get(this.surface.candles) : null;
      if (ohlc) {
        const vol = param.seriesData.get(this.surface.volume);
        this.showBar({ ...ohlc, volume: vol ? vol.value : null }, false);
      } else if (this.lastBar) {
        this.showBar(this.lastBar, true);
      }
    });
  }

  /** Paint the OHLC readout. `live` marks it as the newest replay bar. */
  showBar(bar, live = true) {
    if (live) this.lastBar = bar;
    const up = bar.close >= bar.open;
    $('r-time').textContent = fmtTime(bar.time);
    for (const key of ['open', 'high', 'low', 'close']) {
      $(`r-${key}`).textContent = fmtPrice(bar[key]);
    }
    $('r-vol').textContent = fmtVol(bar.volume);
    $('readout').classList.toggle('up', up);
    $('readout').classList.toggle('down', !up);
  }

  /** Show how far through the dataset the replay cursor sits. */
  showProgress(cursor, total) {
    $('r-pos').textContent = total ? `${cursor.toLocaleString()} / ${total.toLocaleString()}` : '--';
  }

  /** Seed the date box so a jump starts from somewhere sensible. */
  setDate(epochSeconds) {
    $('datetime').value = toInputValue(epochSeconds);
  }

  // --- state ----------------------------------------------------------------

  setMode(mode) {
    this.mode = mode;
    const replaying = mode === 'replay';
    document.body.classList.toggle('replaying', replaying);
    $('replay').textContent = replaying ? 'Exit replay' : 'Replay';
    if (!replaying) this._setPicking(false);
    for (const id of ['play', 'step', 'speed-1', 'speed-2', 'speed-4']) {
      $(id).disabled = !replaying;
    }
  }

  /** Repaint from the SERVER's view of the session (snake_case on the wire). */
  _renderState({ playing, speed, at_end: atEnd }) {
    $('play').textContent = playing ? 'Pause' : 'Play';
    $('play').classList.toggle('active', playing);
    this._renderSpeed(speed);
    $('end').classList.toggle('visible', Boolean(atEnd));
  }

  _renderSpeed(speed) {
    for (const s of [1, 2, 4]) $(`speed-${s}`).classList.toggle('active', s === speed);
  }
}
