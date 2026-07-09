/**
 * Drive replay: play, pause, step, speed.
 *
 * One job: decide *when* the next bar is revealed, and tell listeners it was.
 * It owns the clock and the play state, delegating "what is the next bar" to
 * BarWindow and "draw it" to whoever subscribes. No DOM, no chart calls.
 *
 * The clock is a self-rescheduling timeout rather than setInterval: a step can
 * await a network fill, and setInterval would happily queue callbacks on top of
 * a slow step until playback ran away from itself.
 */

import { BarWindow } from './window.js';

export class ReplayEngine {
  constructor(cfg) {
    this.cfg = cfg;
    this.window = null;
    this.speed = 1;
    this.playing = false;

    this._timer = null;
    this._stepping = false;
    this._listeners = { bar: [], state: [] };
  }

  /** Subscribe to 'bar' ({bar, trimmed, bars}) or 'state' ({playing, speed, atEnd}). */
  on(event, fn) {
    this._listeners[event].push(fn);
    return this;
  }

  _emit(event, payload) {
    this._listeners[event].forEach((fn) => fn(payload));
  }

  _emitState() {
    this._emit('state', {
      playing: this.playing,
      speed: this.speed,
      atEnd: this.window ? this.window.atEnd : false,
    });
  }

  /** Cut back to `startIndex` and show only the history behind it. */
  async start(symbol, timeframe, startIndex) {
    this.pause();
    this.window = new BarWindow(symbol, timeframe, this.cfg);
    const bars = await this.window.seed(startIndex);
    this._emit('bar', { bar: null, trimmed: 0, bars, seeded: true });
    this._emitState();
    return bars;
  }

  /** Reveal exactly one bar. Safe to call while playing or paused. */
  async step() {
    if (!this.window || this._stepping) return null;
    this._stepping = true;
    try {
      const result = await this.window.step();
      if (!result) {
        this.pause();
        this._emitState();
        return null;
      }
      this._emit('bar', { ...result, bars: this.window.bars, seeded: false });
      return result;
    } finally {
      this._stepping = false;
    }
  }

  get intervalMs() {
    return this.cfg.baseStepMs / this.speed;
  }

  /** 1, 2 or 4. Takes effect on the next scheduled bar. */
  setSpeed(speed) {
    this.speed = speed;
    this._emitState();
  }

  play() {
    if (this.playing || !this.window) return;
    this.playing = true;
    this._emitState();
    this._schedule();
  }

  pause() {
    this.playing = false;
    clearTimeout(this._timer);
    this._timer = null;
    this._emitState();
  }

  toggle() {
    this.playing ? this.pause() : this.play();
  }

  /** Reschedule only after the step resolves, so a slow fetch cannot stack up. */
  _schedule() {
    if (!this.playing) return;
    this._timer = setTimeout(async () => {
      if (!this.playing) return;
      const result = await this.step();
      if (result) this._schedule();
    }, this.intervalMs);
  }
}
