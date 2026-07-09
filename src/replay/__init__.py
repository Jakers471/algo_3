"""The server-side replay session: one cursor, one indicator state, many views.

``session`` owns the cursor and the live indicators; ``manager`` keeps sessions
and reaps abandoned ones; ``routes`` exposes control and the snapshot stream.
The chart and the TUI are subscribers, not drivers.
"""
