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

Python is different: a module is imported once, so an edited indicator keeps serving the
old code until the process restarts. Run `python -m src.cli.chart --open --reload` and the
server restarts itself on any `.py` change.

## `chart/` — the replay chart

| Path | Job |
| --- | --- |
| `index.html` | toolbar, chart stage, OHLC readout |
| `css/chart.css` | the dark, gridless theme |
| `js/main.js` | wires the pieces together; decides who talks to whom |
| `js/api.js` | fetch + decode the binary bar records |
| `js/chart.js` | the chart surface: zoom-preserving `rebuild()`, cheap `push()` |
| `js/browse.js` | the non-replay view; backfills older bars as you scroll back |
| `js/overlays.js` | renders the backend's shapes; knows no indicator |
| `js/layers.js` | which layers are visible; filters marks by their `source` |
| `js/layers_panel.js` | the Layers checkbox menu; a thin door onto `layers.js` |
| `js/vertical_lines.js` | a chart primitive: dashed vertical rules with labels |
| `js/format.js` | time / price / volume display strings (UTC, like the bars) |
| `js/replay/stream.js` | control POSTs + the `EventSource` snapshot stream |
| `js/replay/window.js` | the bounded display buffer: append, trim |
| `js/replay/engine.js` | subscribes to snapshots and draws them; owns no clock |
| `js/replay/controls.js` | toolbar → engine wiring; the thin door |

### Why it stays fast

Bars arrive as a flat array of 24-byte records (`uint32` time + five `float32`s), not
JSON — the 1m NQ dataset is ~6.2M bars, and parsing that as JSON would dominate every
frame. `api.js` walks the `ArrayBuffer` with a `DataView`.

Replay never holds the dataset, and it does not own the cursor. The **server** owns the
cursor, the clock and the live indicator state; the browser subscribes to a stream of
snapshots and draws each one. `play` is a POST — bars arrive because the server decided it
was time. That is what lets the TUI watch the same session and show the same row at the
same instant.

The browser keeps a bounded display buffer (~5,000 bars of history behind the cursor) and
drops the oldest chunk once it exceeds its cap. Dropping bars renumbers the chart's
logical indices, so `chart.js` shifts the visible range by the same amount — which is why
the view never jumps and your zoom survives a trim.

### Indicators do not live here

**The chart draws; it never computes.** There is no indicator code in this folder, and
none may be added. Every indicator is computed once, in Python, and arrives over
`/api/overlays` as drawing instructions that `overlays.js` renders without knowing what
they mean. It understands *shapes*, and there are four:

| shape | what it is | drawn by |
|---|---|---|
| `vlines` | a dashed vertical rule with a label | `vertical_lines.js` (a chart primitive) |
| `markers` | a dot or arrow on a bar | lightweight-charts' own markers |
| `segments` | a polyline through `(time, price)` corners, optionally dashed, or offset sideways in pixels | `segments.js` (a chart primitive) |
| `levels` | a horizontal price line across the pane, labelled on the axis | `createPriceLine` |

Not one of them knows what a session, a swing, a break of structure or a volume profile is.
`segments` draws the line between swings, the break of structure, **and** every bin of
the volume profile — the profile arrived on the chart without a single line of frontend
code, because a histogram bin is a segment and that shape already existed. That is what a
shape vocabulary buys.

Every mark also carries a `source` — the indicator that made it. That is the whole basis of
the **Layers** panel: `layers.js` compares strings and drops the hidden ones at the last
step, so this folder can hide a break of structure without ever learning what one is. The
marks themselves are never discarded, which is why toggling a layer on restores the history
it accumulated rather than only what arrives next.

Two flags on a mark change what it *is* rather than how it looks. An `id` marks a shape
re-emitted each bar, one bar longer: the newest replaces the last (the provisional
high/low rails). A `layer` marks a whole group re-emitted wholesale — the volume profile
publishes a different number of bins on every bar, so matching them by id would leave ghost
bins from a range that has since been reset. Everything else is an event, and accumulates.

This is not a style preference. Two implementations of an indicator — one in Python for
the backtest, one in JavaScript for the chart — *will* drift, and the day they drift is
the day the chart contradicts a backtest and you cannot tell which one lied.

Because the backend computes indicators from events at or before the replay cursor, an
indicator structurally cannot see the future. See `BUILD_PLAN.md` phase 2.
