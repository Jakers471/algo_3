# frontend/

Browser code. Kept out of the Python `src/` on purpose — two worlds, cleanly separated.

There is **no build step, no `package.json`, no bundler**. These are plain ES modules
that the browser loads directly, and the one dependency (TradingView Lightweight
Charts, Apache-2.0) is vendored into `chart/vendor/` rather than pulled from a CDN, so
the chart opens with no network access beyond the local server.

## Running

The pages are served by the Python chart server — they cannot be opened as files:

```
python -m src.cli.chart --open      # http://127.0.0.1:8765
```

Opening `chart/index.html` directly from disk fails, and the browser console will say
so: a `file://` page has a null origin, so it is not allowed to load ES modules or
call `/api/*`. Always go through the server.

Edits to HTML/CSS/JS take effect on a plain browser refresh — the server sends
`Cache-Control: no-cache` for static assets, and no build artifact sits in between.

## `chart/` — the replay chart

| Path | Job |
| --- | --- |
| `index.html` | toolbar, chart stage, OHLC readout |
| `css/chart.css` | the dark, gridless theme |
| `js/main.js` | wires the pieces together; **register indicators here** |
| `js/api.js` | fetch + decode the binary bar records |
| `js/chart.js` | the chart surface: zoom-preserving `rebuild()`, cheap `push()` |
| `js/browse.js` | the non-replay view; backfills older bars as you scroll back |
| `js/format.js` | time / price / volume display strings (UTC, like the bars) |
| `js/replay/window.js` | the sliding bar buffer: prefetch ahead, trim behind |
| `js/replay/engine.js` | play / pause / step / speed — owns the clock |
| `js/replay/controls.js` | toolbar → engine wiring; the thin door |
| `js/indicators/registry.js` | the indicator seam |
| `js/indicators/sma.js` | the reference indicator — copy its shape |

### Why it stays fast

Bars arrive as a flat array of 24-byte records (`uint32` time + five `float32`s), not
JSON — the 1m NQ dataset is ~6.2M bars, and parsing that as JSON would dominate every
frame. `api.js` walks the `ArrayBuffer` with a `DataView`.

Replay never holds the dataset. It keeps a bounded window (~5,000 bars of history
behind the cursor), fetches the next run of bars before it needs them, and drops the
oldest chunk once the buffer exceeds its cap. Dropping bars renumbers the chart's
logical indices, so `chart.js` shifts the visible range by the same amount — which is
why the view never jumps and your zoom survives a trim.

### Adding an indicator

Write a module exporting an object with `create` / `compute` / `last`, then register it
in `main.js`:

```js
import { myIndicator } from './indicators/my_indicator.js';
indicators.add(myIndicator(params));
```

It draws in browse mode and in replay, gets a toggle in the toolbar automatically, and
recomputes off the same bounded window the chart draws — so **an indicator cannot see
past the replay cursor.** `last()` returns only the newest point (cheap, called every
step); `compute()` rebuilds the whole series (called on seed and on trim). Omit `last`
and the registry falls back to a full recompute.
