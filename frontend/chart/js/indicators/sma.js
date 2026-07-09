/**
 * Simple moving average - the reference indicator.
 *
 * One job: close-based SMA over a period. It exists as much to demonstrate the
 * registry contract as to be useful: copy this file's shape for any indicator
 * you add (create / compute / last).
 *
 * Note `last()` reads only the final `period` bars, so a replay step costs the
 * same whether the buffer holds 500 bars or 8,000.
 */

const mean = (bars, from, to) => {
  let sum = 0;
  for (let i = from; i < to; i++) sum += bars[i].close;
  return sum / (to - from);
};

/** Build an SMA indicator for the registry. */
export function sma(period, color) {
  return {
    id: `sma${period}`,
    label: `SMA ${period}`,

    create: (chart) => chart.addLineSeries({
      color,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    }),

    compute: (bars) => {
      const points = [];
      for (let i = period - 1; i < bars.length; i++) {
        points.push({ time: bars[i].time, value: mean(bars, i - period + 1, i + 1) });
      }
      return points;
    },

    last: (bars) => {
      if (bars.length < period) return null;
      const i = bars.length - 1;
      return { time: bars[i].time, value: mean(bars, i - period + 1, i + 1) };
    },
  };
}
