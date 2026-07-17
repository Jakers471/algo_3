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

import { nextStudySession } from '../api.js';
import { fmtPrice, fmtTime, fmtVol, fromInputValue, toInputValue } from '../format.js';

const $ = (id) => document.getElementById(id);

export class Controls {
  /**
   * @param {object} deps
   *   { engine, browser, surface, datasets, onStart, onExit, onProfileChange }
   */
  constructor(deps) {
    Object.assign(this, deps);
    this.picking = false;
    // Where the current (or last) replay was cut from. Null until one starts,
    // and deliberately NOT cleared on exit - Restart's whole job is to survive
    // leaving replay.
    this.startedAt = null;

    this._buildSelectors();
    this._wireProfile();
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
    this._fillTimeframes();

    $('symbol').addEventListener('change', () => {
      this._fillTimeframes();
      this._reload();
    });
    // Changing timeframe keeps your place; changing symbol goes to the tail (the
    // datasets do not share a time span, so a preserved time can fall off the end).
    $('timeframe').addEventListener('change', () => this._changeView());
  }

  /** The timeframes this symbol actually has, defaulting to 5m where there is one. */
  _fillTimeframes(prefer) {
    const tfs = Object.keys(this.datasets[$('symbol').value]);
    $('timeframe').innerHTML = tfs.map((t) => `<option>${t}</option>`).join('');
    const wanted = tfs.includes(prefer) ? prefer : '5m';
    $('timeframe').value = tfs.includes(wanted) ? wanted : tfs[0];
  }

  /**
   * Point the selectors at a dataset without loading anything.
   *
   * For a deep link, which must choose the dataset BEFORE it starts a replay -
   * setting the selects and firing 'change' would kick off a browse load that
   * the replay then immediately throws away. Unknown names are ignored rather
   * than fatal: a stale bookmark should open the chart, not a blank page.
   */
  selectDataset(symbol, timeframe) {
    if (symbol && Object.keys(this.datasets).includes(symbol)) {
      $('symbol').value = symbol;
    }
    this._fillTimeframes(timeframe);
  }

  get symbol() { return $('symbol').value; }
  get timeframe() { return $('timeframe').value; }
  get profile() { return $('profile').value; }
  get sessionProfile() { return $('session-profile').value; }

  /**
   * Two INDEPENDENT switches, both gating a volume-at-price fetch: the swing
   * profile's range, and session_stats' own session-wide one. Either can be on
   * without the other - watching only the session's profile must not pay for
   * the swing one's fetch, and the reverse.
   */
  _wireProfile() {
    $('profile').addEventListener('change',
      () => this.onProfileChange(this.profile, this.sessionProfile));
    $('session-profile').addEventListener('change',
      () => this.onProfileChange(this.profile, this.sessionProfile));
    // Both selectors, not just the symbol: whether a profile is possible depends
    // on the symbol (are there ticks?) AND the timeframe (can the store be
    // sliced that fine?). Watching one of them left 15s offering a profile the
    // 30s store cannot answer, and the request died in the indicator.
    $('symbol').addEventListener('change', () => this._syncProfile());
    $('timeframe').addEventListener('change', () => this._syncProfile());
    this._syncProfile();
  }

  /**
   * A profile needs volume at price, and only the ticks have it.
   *
   * Two ways it can be missing. The NT8 bar files record a bar's total volume,
   * its high and its low - never where between them the contracts changed hands,
   * and nothing recovers it. And the tick store was folded at one timeframe: a
   * bar finer than that cannot be sliced out of it, and a bar that is not a whole
   * multiple of it would be handed volume from the bars either side.
   *
   * In both cases BOTH controls are disabled and say why, rather than being
   * offered and quietly drawing nothing - the constraint is about the data, not
   * about which of the two profiles is asking for it.
   */
  _syncProfile() {
    const reason = this._noProfileBecause();
    let changed = false;
    for (const id of ['profile', 'session-profile']) {
      const select = $(id);
      select.disabled = Boolean(reason);
      select.title = reason || 'Volume profile range';
      if (reason && select.value !== 'off') {
        select.value = 'off';
        changed = true;
      }
    }
    if (changed) this.onProfileChange('off', 'off');
  }

  /** Why this symbol/timeframe cannot be profiled, or '' if it can. */
  _noProfileBecause() {
    if (!(this.profileSymbols || []).includes(this.symbol)) {
      return `${this.symbol} has no volume at price - it is a bar file. `
           + 'Use a tick-built symbol.';
    }
    const base = this.profileBaseTimeframe;
    if (base && !divides(base, this.timeframe)) {
      return `volume at price is stored per ${base} bar, so a ${this.timeframe} bar `
           + `cannot be sliced out of it. Use ${base} or a whole multiple of it.`;
    }
    return '';
  }

  _reload() {
    this.engine.pause();
    this.setMode('browse');
    this.onExit();
  }

  /**
   * Change timeframe without losing your place.
   *
   * The old path reloaded the tail and framed it, throwing you to the front.
   * Instead: capture the visible TIME window, leave replay if we were in it, and
   * load the new timeframe centred on that same window. Time is the invariant a
   * bar-size change preserves - a bar index is not, since the same window is a
   * different number of bars once the bars change size.
   */
  async _changeView() {
    const view = this.surface.getVisibleTimeRange();
    this.engine.pause();
    if (this.mode === 'replay') await this.engine.stop();
    this.setMode('browse');
    if (!view) { await this.onExit(); return; }   // nothing on screen to preserve
    await this.browser.loadAround(this.symbol, this.timeframe, view);
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
      this.startAt(fromInputValue(value));
    });

    // Click-to-cut: the chart click hands back the bar's time, which the server
    // turns into a dataset index. Replay starts there.
    this.surface.onClick((param) => {
      if (!this.picking || !param.time) return;
      this._setPicking(false);
      this.startAt(param.time);
    });

    // Back to where this replay began. The moment survives leaving replay, so
    // studying a session is: watch it, exit to look around, restart, watch it
    // again - rather than exiting and hunting for the bar a second time. The
    // date box cannot serve as the memory: showBar() rewrites it every bar, so
    // by the end of a replay it holds the last bar, not the first.
    $('restart').disabled = true;   // nothing to go back to until a replay starts
    $('restart').addEventListener('click', () => {
      if (this.startedAt == null) return;
      this.startAt(this.startedAt);
    });

    // Session-to-session, without a terminal round-trip. The study loop is
    // "look at one, form a view, look at another"; a loop that costs a trip to
    // a shell per iteration is a loop that gets run five times and abandoned.
    $('study-next').addEventListener('click', () => this._studyNext());

    $('fit').addEventListener('click', () => this.surface.fit());
  }

  /** Open a random explore-side session. The server refuses to serve a sealed one. */
  async _studyNext() {
    const button = $('study-next');
    button.disabled = true;
    try {
      const pick = await nextStudySession(this.symbol, this.timeframe,
                                          $('study-session').value);
      $('study-label').textContent =
        `${pick.session} ${fmtTime(pick.at).slice(0, 16)} - explore, 1 of ${pick.explore_total}`;
      $('study-label').classList.remove('error');
      await this.startAt(pick.at);
    } catch (err) {
      // Most likely: this symbol has no seal, or no explore sessions. Say it on
      // the chart rather than only in a console nobody has open.
      $('study-label').textContent = String(err.message || err);
      $('study-label').classList.add('error');
    } finally {
      button.disabled = false;
    }
  }

  /**
   * Enter replay at a moment, remembering it for Restart.
   *
   * Every path into replay comes through here - the date box, a click on the
   * chart, and a deep link - so none of them can forget to record where it
   * began.
   */
  async startAt(epochSeconds) {
    this.startedAt = epochSeconds;
    $('restart').disabled = false;
    await this.onStart(epochSeconds);
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
    // `restart` is deliberately absent: the transport controls are meaningless
    // outside replay, but Restart's entire purpose is to get you back INTO it.
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


const UNIT_SECONDS = { s: 1, m: 60, h: 3600, d: 86400 };

/** Seconds in a timeframe: '15m' -> 900. Mirrors overlays.step_seconds. */
function seconds(timeframe) {
  return parseInt(timeframe, 10) * UNIT_SECONDS[timeframe.slice(-1)];
}

/** Does `base` fold a whole number of times into `timeframe`? */
function divides(base, timeframe) {
  if (!timeframe) return true;
  const a = seconds(base);
  const b = seconds(timeframe);
  return b >= a && b % a === 0;
}
