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
| `js/main.js` | wires the pieces together; decides who talks to whom |
| `js/api.js` | fetch + decode the binary bar records |
| `js/chart.js` | the chart surface: zoom-preserving `rebuild()`, cheap `push()` |
| `js/browse.js` | the non-replay view; backfills older bars as you scroll back |
| `js/format.js` | time / price / volume display strings (UTC, like the bars) |
| `js/replay/window.js` | the sliding bar buffer: prefetch ahead, trim behind |
| `js/replay/engine.js` | play / pause / step / speed — owns the clock |
| `js/replay/controls.js` | toolbar → engine wiring; the thin door |

### Why it stays fast

Bars arrive as a flat array of 24-byte records (`uint32` time + five `float32`s), not
JSON — the 1m NQ dataset is ~6.2M bars, and parsing that as JSON would dominate every
frame. `api.js` walks the `ArrayBuffer` with a `DataView`.

Replay never holds the dataset. It keeps a bounded window (~5,000 bars of history
behind the cursor), fetches the next run of bars before it needs them, and drops the
oldest chunk once the buffer exceeds its cap. Dropping bars renumbers the chart's
logical indices, so `chart.js` shifts the visible range by the same amount — which is
why the view never jumps and your zoom survives a trim.

### Indicators do not live here

**The chart draws; it never computes.** There is no indicator code in this folder, and
none may be added. Every indicator is computed once, in Python, and will arrive over the
wire as drawing instructions (a line, a shaded band, a marker) that the chart renders
without knowing what they mean.

This is not a style preference. Two implementations of an indicator — one in Python for
the backtest, one in JavaScript for the chart — *will* drift, and the day they drift is
the day the chart contradicts a backtest and you cannot tell which one lied.

Because the backend computes indicators from events at or before the replay cursor, an
indicator structurally cannot see the future. See `BUILD_PLAN.md` phase 2.
