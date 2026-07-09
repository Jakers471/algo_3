/**
 * Talk to the chart server.
 *
 * One job: fetch, and turn the raw 24-byte bar records into the objects
 * lightweight-charts wants. Nothing here knows about charts or replay.
 *
 * Bars arrive as a flat little-endian record array, not JSON: at 1m there are
 * over six million of them, and JSON.parse would dominate every frame budget.
 * A DataView walk over an ArrayBuffer costs microseconds per thousand bars.
 */

// Must match src/chart/packer.py BAR_DTYPE. Changing this without changing that
// silently misreads every candle - the fields are positional, not named.
const BAR_BYTES = 40;
const LITTLE_ENDIAN = true;

/**
 * NaN on the wire means the dataset cannot supply this field, not that it is
 * zero. The NT8 bar files have no order flow and never can. Returning null
 * keeps "absent" distinguishable from "balanced" all the way to the screen.
 */
const optional = (value) => (Number.isNaN(value) ? null : value);

/** Decode a raw /api/bars payload into bar objects (time in epoch seconds, UTC). */
export function decodeBars(buffer) {
  const view = new DataView(buffer);
  const n = Math.floor(buffer.byteLength / BAR_BYTES);
  const bars = new Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * BAR_BYTES;
    bars[i] = {
      time: view.getUint32(o, LITTLE_ENDIAN),
      open: view.getFloat32(o + 4, LITTLE_ENDIAN),
      high: view.getFloat32(o + 8, LITTLE_ENDIAN),
      low: view.getFloat32(o + 12, LITTLE_ENDIAN),
      close: view.getFloat32(o + 16, LITTLE_ENDIAN),
      volume: view.getFloat32(o + 20, LITTLE_ENDIAN),
      delta: optional(view.getFloat32(o + 24, LITTLE_ENDIAN)),
      buyVolume: optional(view.getFloat32(o + 28, LITTLE_ENDIAN)),
      sellVolume: optional(view.getFloat32(o + 32, LITTLE_ENDIAN)),
      trades: optional(view.getFloat32(o + 36, LITTLE_ENDIAN)),
    };
  }
  return bars;
}

async function getJSON(path, params) {
  const url = new URL(path, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

/**
 * The server's replay dials (config/chart.py is the single source of truth).
 * Snake_case on the wire, camelCase in JS.
 */
export async function getConfig() {
  const camel = (obj) => Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [
      k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
      v && typeof v === 'object' && !Array.isArray(v) ? camel(v) : v,
    ]),
  );
  return camel(await getJSON('/api/config'));
}

/** Every packed symbol/timeframe with its bar count and time span. */
export const getDatasets = () => getJSON('/api/datasets');

/** The bar index at or after an epoch-second timestamp. */
export const locate = (symbol, timeframe, time) =>
  getJSON('/api/locate', { symbol, timeframe, time: Math.floor(time) });

/**
 * Drawing instructions for bars `[start, start+count)`.
 *
 * Python computed these. The chart renders them without knowing what they mean -
 * pass the range you have REVEALED and the drawing cannot leak the future.
 */
export const getOverlays = (symbol, timeframe, start, count, profile = 'off') =>
  getJSON('/api/overlays', {
    symbol, timeframe, profile,
    start: Math.max(0, Math.floor(start)), count: Math.floor(count),
  });

/**
 * Bars `[start, start+count)`.
 *
 * The server clamps, so the returned `start` and `bars.length` are the truth
 * about what came back - never assume the request was honored verbatim.
 */
export async function getBars(symbol, timeframe, start, count) {
  const url = new URL('/api/bars', window.location.origin);
  url.searchParams.set('symbol', symbol);
  url.searchParams.set('timeframe', timeframe);
  url.searchParams.set('start', Math.max(0, Math.floor(start)));
  url.searchParams.set('count', Math.floor(count));

  const res = await fetch(url);
  if (!res.ok) throw new Error(`/api/bars -> ${res.status} ${await res.text()}`);
  const buffer = await res.arrayBuffer();
  return {
    bars: decodeBars(buffer),
    start: Number(res.headers.get('X-Start')),
    total: Number(res.headers.get('X-Total')),
  };
}
