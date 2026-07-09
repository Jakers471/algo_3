/**
 * Format values for the readout.
 *
 * One job: numbers and epochs in, display strings out. Times render in UTC
 * because that is what the bars carry - the Parquet store is UTC end-to-end,
 * and silently localizing here would make the clock lie about the session.
 */

const pad = (n) => String(n).padStart(2, '0');

/** Epoch seconds -> "2020-03-16 13:30 UTC". */
export function fmtTime(epochSeconds) {
  if (!epochSeconds) return '--';
  const d = new Date(epochSeconds * 1000);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} `
       + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`;
}

/** Epoch seconds -> the value a <input type="datetime-local"> expects. */
export function toInputValue(epochSeconds) {
  const d = new Date(epochSeconds * 1000);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
       + `T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

/** A datetime-local value -> epoch seconds, read as UTC (not the browser's zone). */
export function fromInputValue(value) {
  return Math.floor(Date.parse(`${value}:00Z`) / 1000);
}

export const fmtPrice = (n) => (n == null ? '--' : n.toFixed(2));

export const fmtVol = (n) => {
  if (n == null) return '--';
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(Math.round(n));
};
