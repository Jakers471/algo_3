/**
 * Talk to the server-side replay session.
 *
 * One job: send control (start / step / play / pause / stop) and receive the
 * snapshot stream. The cursor, the indicator state, and the clock all live on
 * the server; this file owns none of them.
 *
 * That is the whole point. The chart and the TUI subscribe to the same stream,
 * so they show the same row at the same instant, and a third view costs nothing.
 * Nothing here computes; nothing here decides when the next bar arrives.
 */

/**
 * A stable id for this browser, surviving refreshes.
 *
 * Without it, a refresh forgets the session id and starts a second replay
 * beside the first. They pile up until the server's idle reaper notices, and a
 * table attaching in the meantime cannot tell which one is "the" replay.
 */
function clientId() {
  let id = localStorage.getItem('algo3.clientId');
  if (!id) {
    id = `chart-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem('algo3.clientId', id);
  }
  return id;
}

const post = async (path, body) => {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const err = new Error(`${path} -> ${res.status} ${await res.text()}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
};

export class ReplayStream {
  constructor() {
    this.sessionId = null;
    this._source = null;
    this._handlers = { snapshot: [], state: [], lost: [] };
  }

  /**
   * Subscribe to 'snapshot' (a row), 'state' (playing / speed / at_end), or
   * 'lost' (the server no longer has our session; re-seed if you want one).
   */
  on(event, fn) {
    this._handlers[event].push(fn);
    return this;
  }

  _emit(event, payload) {
    this._handlers[event].forEach((fn) => fn(payload));
  }

  /**
   * Cut to `index` and open the stream.
   *
   * Returns the seed: the warmed-up window bounds and the drawings the warmup
   * produced. The server replayed those bars silently, so the indicators hold
   * exactly what they would have held had we played into this point.
   */
  async start(symbol, timeframe, index) {
    // Hand the old id back so the server can retire it: an orphaned session
    // would keep a stepping thread alive behind a view that moved on.
    const seed = await post('/api/replay/start', {
      symbol, timeframe, index, replace: this.sessionId, owner: clientId(),
    });
    this.sessionId = seed.session;
    this._open();
    return seed;
  }

  _open() {
    this.close();
    this._source = new EventSource(`/api/replay/stream?session=${this.sessionId}`);
    this._source.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.state) this._emit('state', payload.state);
      else this._emit('snapshot', payload);
    };
    this._source.onerror = async () => {
      // EventSource reconnects on its own, forever, with no way to switch that
      // off. When the session still exists that is exactly what we want - the
      // cursor and indicator state survive the gap. When it does not, every
      // retry 404s and the retries never stop. Sessions live in memory, so
      // `--reload` restarting the server retires all of them at once; that is
      // the common way to arrive here. Ask once, and if we have been retired,
      // close the socket and say so rather than storm.
      if (await this._alive()) {
        console.warn('replay stream interrupted; EventSource will retry');
      } else {
        this._lost();
      }
    };
  }

  /** Does the server still know our session? */
  async _alive() {
    if (!this.sessionId) return false;
    try {
      const res = await fetch('/api/replay/sessions');
      if (!res.ok) return false;
      const { sessions } = await res.json();
      return sessions.some((s) => s.id === this.sessionId);
    } catch {
      return false;   // the server is unreachable; retrying the stream is no better
    }
  }

  /** Our session is gone. Stop talking to it, and tell whoever cares. */
  _lost() {
    const id = this.sessionId;
    this.close();
    this.sessionId = null;
    if (id) this._emit('lost', { session: id });
  }

  /**
   * Send one control command.
   *
   * Two guards. Without a session there is nobody to command, so we do not POST
   * `session: null` and collect a 404 for it. And a 404 from a command we *did*
   * address means the session was retired underneath us - the same condition the
   * stream discovers, reached by a different door.
   */
  async _control(send) {
    if (!this.sessionId) return null;
    try {
      return await send();
    } catch (err) {
      if (err.status === 404) { this._lost(); return null; }
      throw err;
    }
  }

  step(n = 1) { return this._control(() => post('/api/replay/step', { session: this.sessionId, n })); }
  play(speed) { return this._control(() => post('/api/replay/play', { session: this.sessionId, speed })); }
  pause() { return this._control(() => post('/api/replay/pause', { session: this.sessionId })); }

  async stop() {
    this.close();
    if (this.sessionId) {
      const id = this.sessionId;
      this.sessionId = null;
      await post('/api/replay/stop', { session: id }).catch(() => {});
    }
  }

  close() {
    if (this._source) { this._source.close(); this._source = null; }
  }
}
