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

const post = async (path, body) => {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  return res.json();
};

export class ReplayStream {
  constructor() {
    this.sessionId = null;
    this._source = null;
    this._handlers = { snapshot: [], state: [] };
  }

  /** Subscribe to 'snapshot' (a row) or 'state' (playing / speed / at_end). */
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
      symbol, timeframe, index, replace: this.sessionId,
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
    this._source.onerror = () => {
      // EventSource reconnects on its own. The session outlives the gap by
      // design, so the cursor and indicator state survive a refresh.
      console.warn('replay stream interrupted; EventSource will retry');
    };
  }

  step(n = 1) { return post('/api/replay/step', { session: this.sessionId, n }); }
  play(speed) { return post('/api/replay/play', { session: this.sessionId, speed }); }
  pause() { return post('/api/replay/pause', { session: this.sessionId }); }

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
