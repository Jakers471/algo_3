/**
 * Drive replay from the browser side: ask the server, draw what comes back.
 *
 * One job: hold the display buffer and the accumulated marks, translate a
 * snapshot into the cheapest possible redraw, and forward transport commands to
 * the server.
 *
 * It does not own the clock. It does not step anything. `play` is a POST, and
 * bars arrive because the server decided it was time - which is exactly why a
 * TUI watching the same session sees the same bar at the same moment.
 *
 * Three redraw paths, cheapest first: append one bar (the common case), rebuild
 * after a buffer trim (holding the zoom), or rebuild from a fresh seed.
 */

import { getBars } from '../api.js';
import { BarBuffer } from './window.js';
import { ReplayStream } from './stream.js';

// A server that cannot seed will not seed on the next attempt either.
const MAX_RECOVERY_ATTEMPTS = 3;

export class ReplayEngine {
  constructor(cfg, surface, layers) {
    this.cfg = cfg;
    this.surface = surface;
    this.layers = layers;
    this.buffer = new BarBuffer(cfg);
    this.stream = new ReplayStream();
    if (layers) layers.onChange(() => { if (this.marks.length) this._drawMarks(); });

    this.marks = [];
    this.playing = false;
    this.speed = 1;
    this.atEnd = false;

    // What we are replaying, so a lost session can be rebuilt where it stood.
    this.symbol = null;
    this.timeframe = null;
    this.profile = 'off';
    this._recovering = false;
    this._recoveryFailures = 0;
    this._generation = 0;   // guards a slow start against a newer one

    this._listeners = { bar: [], state: [] };

    this.stream.on('snapshot', (snap) => this._onSnapshot(snap));
    this.stream.on('state', (state) => {
      this.playing = state.playing;
      this.speed = state.speed;
      this.atEnd = state.at_end;
      this._emit('state', state);
    });
    this.stream.on('lost', () => this._recover());
  }

  /**
   * The server forgot our session; seed a new one at the bar we had reached.
   *
   * Sessions live in the server's memory, so `--reload` wipes them mid-replay.
   * Re-seeding replays the warmup silently, which is precisely how a seek works
   * - so the indicators come back holding exactly what they held before, and the
   * chart continues instead of stranding the user on a dead stream.
   */
  async _recover() {
    if (this._recovering || !this.symbol) return;
    if (this._recoveryFailures >= MAX_RECOVERY_ATTEMPTS) return;

    this._recovering = true;
    try {
      await this.start(this.symbol, this.timeframe, this.cursor + 1);
      this._recoveryFailures = 0;
      console.warn('replay session was retired; re-seeded at the same bar');
    } catch (err) {
      // A server that cannot seed will not seed on the next try either. Retrying
      // it forever is the storm this whole mechanism exists to prevent, only now
      // it is us making the requests.
      this._recoveryFailures++;
      this.stream.close();
      console.error(
        `could not re-seed the replay (${this._recoveryFailures}/${MAX_RECOVERY_ATTEMPTS})`,
        err);
    } finally {
      this._recovering = false;
    }
  }

  on(event, fn) {
    this._listeners[event].push(fn);
    return this;
  }

  _emit(event, payload) {
    this._listeners[event].forEach((fn) => fn(payload));
  }

  get cursor() { return this.buffer.cursor; }
  get total() { return this.buffer.total; }

  /**
   * Cut back to `index`, draw the history, and start listening.
   *
   * The server seeds its indicators over the same window it hands us marks for,
   * so what we draw and what it believes are the same thing.
   */
  async start(symbol, timeframe, index, profile = this.profile) {
    this.symbol = symbol;
    this.timeframe = timeframe;
    // The profile indicator's state IS the range it has accumulated, so a change
    // of range is a new session, not a new setting on this one.
    this.profile = profile;
    const generation = ++this._generation;

    const seed = await this.stream.start(symbol, timeframe, index, profile);

    // History bars still come over the binary endpoint: 5,000 bars is 120KB of
    // packed records, versus megabytes of JSON inside a snapshot.
    const count = seed.cursor + 1 - seed.first_index;
    const { bars } = await getBars(symbol, timeframe, seed.first_index, count);

    // Two awaits above; a newer start may have overtaken us. Seeding the buffer
    // now would replace its bars with older ones while the newer session's
    // snapshots are already arriving - and the chart would be handed a bar older
    // than its last.
    if (generation !== this._generation) return seed;

    this.buffer.seed(bars, seed.first_index, seed.total);
    this.marks = flattenOverlays(seed.overlays);

    this.surface.rebuild(bars);
    this._drawMarks();
    this.surface.fit();

    this._emit('bar', { bar: null, bars, seeded: true });
    return seed;
  }

  _onSnapshot(snap) {
    // The session publishes a row per rung of the ladder - the same market at a
    // coarser scale. This chart draws ONE timeframe, and a 15m bar appended to a
    // 30s series would be a bar out of order. The tables read the other rungs.
    if (snap.rung && snap.rung !== this.timeframe) return;

    const bar = { time: snap.time, ...snap.bar };

    // Replay time only ever moves forward. A snapshot at or before the newest
    // bar we hold is a straggler from a session that has been retired - it was
    // already in flight when we cut back and seeded a new one. Appending it
    // would hand lightweight-charts a bar older than its last ("Cannot update
    // oldest data") and, worse, draw a bar the current cursor has not revealed.
    if (this.buffer.bars.length && bar.time <= this.buffer.newestTime) return;

    const trimmed = this.buffer.push(bar);

    if (snap.marks.length) {
      // Two kinds of redraw, and everything else is an event that accumulates.
      //
      // An `id` names one shape re-emitted each bar, one bar longer: the newest
      // replaces the last. A `layer` names a GROUP re-emitted wholesale - the
      // volume profile publishes a different number of bins on every bar, so
      // matching them by id would leave ghost bins from a range already reset.
      const layers = new Set(snap.marks.map((m) => m.layer).filter(Boolean));
      const ids = new Set(snap.marks.map((m) => m.id).filter(Boolean));
      const stale = (m) => (m.layer && layers.has(m.layer)) || (m.id && ids.has(m.id));
      this.marks = (layers.size || ids.size ? this.marks.filter((m) => !stale(m)) : this.marks)
        .concat(snap.marks);
    }
    if (trimmed) {
      // Marks scrolled off the front can never be drawn again; dropping them
      // keeps this list bounded over a long replay.
      const oldest = this.buffer.oldestTime;
      this.marks = this.marks.filter((m) => m.time >= oldest);
      this.surface.rebuild(this.buffer.bars, trimmed);
    } else {
      this.surface.push(bar);
    }
    // setMarkers replaces the whole set, so it must be redrawn on a trim too.
    if (snap.marks.length || trimmed) this._drawMarks();

    this.atEnd = snap.at_end;
    this._emit('bar', { bar, bars: this.buffer.bars, seeded: false, snapshot: snap });
  }

  // --- transport: every one of these is a request, not a local decision ---

  step() { return this.stream.step(1); }
  play() { return this.stream.play(this.speed); }
  pause() { return this.stream.pause(); }
  toggle() { return this.playing ? this.pause() : this.play(); }

  setSpeed(speed) {
    this.speed = speed;
    // Changing speed mid-play must not stop playback; the server re-paces.
    return this.playing ? this.stream.play(speed) : Promise.resolve();
  }

  /** Split the accumulated marks by shape and hand each to its renderer.
   *
   * Hidden layers are dropped here, at the last step, and never from `this.marks`
   * - so turning a layer back on redraws the history it already accumulated
   * rather than the fragment that arrived after the click.
   */
  _drawMarks() {
    const drawn = this.layers ? this.layers.filter(this.marks) : this.marks;
    this.surface.setVerticalLines(drawn.filter((m) => m.kind === 'vline'));
    this.surface.setMarkers(drawn.filter((m) => m.kind === 'marker'));
    this.surface.setSegments(drawn.filter((m) => m.kind === 'segment'));
    this.surface.setPriceLines(drawn.filter((m) => m.kind === 'level'));
  }

  stop() {
    this.marks = [];
    this.surface.setVerticalLines([]);
    this.surface.setMarkers([]);
    this.surface.setSegments([]);
    this.surface.setPriceLines([]);
    return this.stream.stop();
  }
}

/**
 * Flatten the seed's grouped overlay specs back into flat marks.
 *
 * The seed arrives grouped by shape (browse mode wants it that way); a replay
 * step delivers flat marks. Keeping one flat list means the trim filter and the
 * redraw do not care which arrived how.
 */
function flattenOverlays(overlays) {
  const marks = [];
  for (const overlay of overlays || []) {
    if (overlay.kind === 'vlines') marks.push(...overlay.lines.map((l) => ({ ...l, kind: 'vline' })));
    else if (overlay.kind === 'markers') marks.push(...overlay.markers);
    else if (overlay.kind === 'segments') marks.push(...overlay.segments);
  }
  return marks;
}
